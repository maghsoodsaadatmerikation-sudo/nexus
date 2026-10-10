//! Conservative single-host request markers. A reservation is synced before delegation.
use crate::RequestStatus;
use std::{
    collections::HashMap,
    fs::{self, File, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
};

pub(crate) struct RequestStore {
    root: PathBuf,
}

impl RequestStore {
    pub(crate) fn open(root: &Path) -> io::Result<(Self, HashMap<String, RequestStatus>)> {
        let root = if root.is_absolute() {
            root.to_owned()
        } else {
            std::env::current_dir()?.join(root)
        };
        fs::create_dir_all(&root)?;
        // Persist every newly created ancestor as well as the marker directory.
        for ancestor in root.ancestors() {
            File::open(ancestor)?.sync_all()?;
        }
        let store = Self {
            root: root.to_owned(),
        };
        let mut statuses = HashMap::new();
        for entry in fs::read_dir(root)? {
            let entry = entry?;
            let name = entry.file_name().into_string().map_err(|_| invalid())?;
            if !name.is_ascii()
                || !entry.file_type()?.is_file()
                || name.len() % 2 != 0
                || name.len() > 200
            {
                return Err(invalid());
            }
            let bytes = (0..name.len())
                .step_by(2)
                .map(|i| u8::from_str_radix(&name[i..i + 2], 16).map_err(|_| invalid()))
                .collect::<io::Result<Vec<_>>>()?;
            let id = String::from_utf8(bytes).map_err(|_| invalid())?;
            if store.path(&id).file_name() != Some(entry.file_name().as_os_str()) {
                return Err(invalid());
            }
            if entry.metadata()?.len() > 8 {
                return Err(invalid());
            }
            let marker = fs::read(entry.path())?;
            let status = if marker == b"pending\n" {
                RequestStatus::Pending
            } else if marker.is_empty() || b"pending\n".starts_with(&marker) {
                RequestStatus::Indeterminate
            } else {
                return Err(invalid());
            };
            statuses.insert(id, status);
        }
        Ok((store, statuses))
    }

    fn path(&self, id: &str) -> PathBuf {
        self.root.join(
            id.as_bytes()
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect::<String>(),
        )
    }

    pub(crate) fn reserve(&self, id: &str) -> io::Result<()> {
        let file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(self.path(id))?;
        file.sync_all()?;
        File::open(&self.root)?.sync_all()
    }

    pub(crate) fn pending(&self, id: &str) -> io::Result<()> {
        // A torn write recovers conservatively as indeterminate, never as accepted.
        let mut file = OpenOptions::new().write(true).open(self.path(id))?;
        file.write_all(b"pending\n")?;
        file.sync_all()
    }
}

fn invalid() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "invalid request marker")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        io::{BufRead, BufReader},
        process::{Command, Stdio},
    };

    #[test]
    fn crash_writer() {
        let Some(root) = std::env::var_os("NEXUS_TEST_CRASH_STORE") else {
            return;
        };
        let (store, _) = RequestStore::open(Path::new(&root)).unwrap();
        store.reserve("interrupted").unwrap();
        println!("RESERVATION_SYNCED");
        std::io::stdout().flush().unwrap();
        loop {
            std::thread::park();
        }
    }

    #[test]
    fn killed_writer_recovers_reservation_as_indeterminate() {
        let root = std::env::temp_dir().join(format!("nexus-crash-{}", uuid::Uuid::new_v4()));
        let mut child = Command::new(std::env::current_exe().unwrap())
            .args([
                "--exact",
                "request_store::tests::crash_writer",
                "--nocapture",
            ])
            .env("NEXUS_TEST_CRASH_STORE", &root)
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let mut output = BufReader::new(child.stdout.take().unwrap());
        let mut line = String::new();
        loop {
            line.clear();
            assert!(output.read_line(&mut line).unwrap() > 0);
            if line.trim() == "RESERVATION_SYNCED" {
                break;
            }
        }
        child.kill().unwrap();
        assert!(!child.wait().unwrap().success());
        let (store, recovered) = RequestStore::open(&root).unwrap();
        assert_eq!(recovered["interrupted"], RequestStatus::Indeterminate);
        assert_eq!(
            store.reserve("interrupted").unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        fs::remove_dir_all(root).unwrap();
    }
}

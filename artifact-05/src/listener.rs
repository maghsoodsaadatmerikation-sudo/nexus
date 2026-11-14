//! Optional supervisor-owned socket activation; ordinary direct binding stays available.
use std::{io, net::SocketAddr};

fn invalid(message: &'static str) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidInput, message)
}

pub async fn open(addr: SocketAddr) -> io::Result<tokio::net::TcpListener> {
    match std::env::var_os("NEXUS_LISTEN_FD") {
        None => tokio::net::TcpListener::bind(addr).await,
        Some(value) => {
            let fd = value
                .to_str()
                .and_then(|s| s.parse::<i32>().ok())
                .ok_or_else(|| invalid("invalid inherited listener descriptor"))?;
            from_inherited(fd, addr)
        }
    }
}

#[cfg(unix)]
fn duplicate_listener(fd: i32, expected: SocketAddr) -> io::Result<std::net::TcpListener> {
    use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
    if fd < 3 {
        return Err(invalid("listener descriptor must not be standard I/O"));
    }
    // Duplicate first: a bad configured descriptor never transfers ownership of
    // another Rust runtime resource into a new owner. The duplicate is CLOEXEC.
    let copied = unsafe { libc::fcntl(fd, libc::F_DUPFD_CLOEXEC, 3) };
    if copied < 0 {
        return Err(io::Error::last_os_error());
    }
    // SAFETY: fcntl returned a new, valid descriptor exclusively owned here.
    let owned = unsafe { OwnedFd::from_raw_fd(copied) };
    let mut accepting: libc::c_int = 0;
    let mut size = std::mem::size_of_val(&accepting) as libc::socklen_t;
    // SAFETY: owned stays live; the output pointer and length refer to accepting.
    let code = unsafe {
        libc::getsockopt(
            owned.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_ACCEPTCONN,
            (&mut accepting as *mut libc::c_int).cast(),
            &mut size,
        )
    };
    if code != 0 {
        return Err(io::Error::last_os_error());
    }
    if accepting != 1 {
        return Err(invalid("inherited socket is not listening"));
    }
    let listener = std::net::TcpListener::from(owned);
    if listener.local_addr()? != expected {
        return Err(invalid("inherited listener address mismatch"));
    }
    listener.set_nonblocking(true)?;
    Ok(listener)
}

#[cfg(unix)]
fn from_inherited(fd: i32, expected: SocketAddr) -> io::Result<tokio::net::TcpListener> {
    let listener = tokio::net::TcpListener::from_std(duplicate_listener(fd, expected)?)?;
    // The validated original was passed by the supervisor, before the gateway
    // created any listening socket. Tokio now owns its independent duplicate.
    // SAFETY: close exactly that inherited listener after successful adoption.
    unsafe {
        libc::close(fd);
    }
    Ok(listener)
}

#[cfg(not(unix))]
fn from_inherited(_: i32, _: SocketAddr) -> io::Result<tokio::net::TcpListener> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "inherited listeners require Unix",
    ))
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::{
        net::{TcpListener, TcpStream, UdpSocket},
        os::fd::AsRawFd,
    };

    #[test]
    fn preserves_reserved_socket_identity() {
        let original = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = original.local_addr().unwrap();
        let duplicate = duplicate_listener(original.as_raw_fd(), addr).unwrap();
        assert_eq!(duplicate.local_addr().unwrap(), addr);
        let _client = TcpStream::connect(addr).unwrap();
        let _accepted = duplicate.accept().unwrap();
        drop(duplicate);
        assert_eq!(original.local_addr().unwrap(), addr);
    }

    #[test]
    fn refuses_wrong_address_without_consuming_the_original() {
        let original = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = original.local_addr().unwrap();
        assert!(duplicate_listener(original.as_raw_fd(), SocketAddr::new(addr.ip(), 0)).is_err());
        assert_eq!(original.local_addr().unwrap(), addr);
    }

    #[test]
    fn refuses_non_listeners_and_invalid_descriptors() {
        let addr = "127.0.0.1:3000".parse().unwrap();
        for fd in [-1, 0, 1, 2, i32::MAX] {
            assert!(duplicate_listener(fd, addr).is_err());
        }
        let file = std::fs::File::open("/dev/null").unwrap();
        assert!(duplicate_listener(file.as_raw_fd(), addr).is_err());
        let udp = UdpSocket::bind("127.0.0.1:0").unwrap();
        assert!(duplicate_listener(udp.as_raw_fd(), udp.local_addr().unwrap()).is_err());
        let server = TcpListener::bind("127.0.0.1:0").unwrap();
        let _client = TcpStream::connect(server.local_addr().unwrap()).unwrap();
        let (connected, _) = server.accept().unwrap();
        assert!(duplicate_listener(connected.as_raw_fd(), connected.local_addr().unwrap()).is_err());
    }
}

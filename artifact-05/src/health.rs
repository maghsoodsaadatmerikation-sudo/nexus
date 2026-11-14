//! Bounded, credential-free liveness for the configured container listener.
use serde::Deserialize;
use std::{
    io::{self, Read, Write},
    net::{IpAddr, Ipv4Addr, Ipv6Addr, SocketAddr, TcpStream},
    time::{Duration, Instant},
};

const LIMIT: usize = 8192;
const REQUEST: &[u8] = b"GET /livez HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n";

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Liveness {
    status: String,
}

fn invalid() -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, "invalid liveness response")
}

fn target(mut addr: SocketAddr) -> io::Result<SocketAddr> {
    if addr.port() == 0 {
        return Err(invalid());
    }
    if addr.ip().is_unspecified() {
        addr.set_ip(match addr.ip() {
            IpAddr::V4(_) => Ipv4Addr::LOCALHOST.into(),
            IpAddr::V6(_) => Ipv6Addr::LOCALHOST.into(),
        });
    }
    Ok(addr)
}

fn validate(response: &[u8]) -> io::Result<()> {
    if response.len() > LIMIT {
        return Err(invalid());
    }
    let split = response
        .windows(4)
        .position(|p| p == b"\r\n\r\n")
        .ok_or_else(invalid)?;
    let head = std::str::from_utf8(&response[..split]).map_err(|_| invalid())?;
    let mut lines = head.split("\r\n");
    let status: Vec<_> = lines
        .next()
        .ok_or_else(invalid)?
        .split_whitespace()
        .collect();
    if status.len() < 2 || !["HTTP/1.0", "HTTP/1.1"].contains(&status[0]) || status[1] != "200" {
        return Err(invalid());
    }
    let body = &response[split + 4..];
    let mut length = None;
    for line in lines {
        let (name, value) = line.split_once(':').ok_or_else(invalid)?;
        if name.eq_ignore_ascii_case("transfer-encoding") {
            return Err(invalid());
        }
        if name.eq_ignore_ascii_case("content-length") {
            let value = value.trim();
            if length.is_some() || value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
                return Err(invalid());
            }
            length = Some(value.parse::<usize>().map_err(|_| invalid())?);
        }
    }
    if body.len() > 4096 || length != Some(body.len()) {
        return Err(invalid());
    }
    let object_start = body.iter().copied().find(|b| !b.is_ascii_whitespace());
    if object_start != Some(b'{') {
        return Err(invalid());
    }
    let result: Liveness = serde_json::from_slice(body).map_err(|_| invalid())?;
    if result.status != "alive" {
        return Err(invalid());
    }
    Ok(())
}

pub fn from_env() -> io::Result<()> {
    let addr = std::env::var("NEXUS_BIND_ADDR").unwrap_or_else(|_| "127.0.0.1:3000".to_owned());
    let addr = target(addr.parse().map_err(|_| invalid())?)?;
    let deadline = Instant::now() + Duration::from_secs(2);
    let mut stream = TcpStream::connect_timeout(&addr, Duration::from_millis(500))?;
    let mut sent = 0;
    while sent < REQUEST.len() {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .ok_or_else(invalid)?;
        stream.set_write_timeout(Some(remaining.min(Duration::from_millis(500))))?;
        match stream.write(&REQUEST[sent..]) {
            Ok(0) => return Err(invalid()),
            Ok(n) => sent += n,
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(error),
        }
    }
    let mut response = Vec::new();
    let mut buffer = [0_u8; 1024];
    loop {
        let remaining = deadline
            .checked_duration_since(Instant::now())
            .ok_or_else(invalid)?;
        stream.set_read_timeout(Some(remaining.min(Duration::from_millis(500))))?;
        match stream.read(&mut buffer) {
            Ok(0) => break,
            Ok(n) => {
                if response.len() + n > LIMIT {
                    return Err(invalid());
                }
                response.extend_from_slice(&buffer[..n]);
            }
            Err(error) if error.kind() == io::ErrorKind::Interrupted => continue,
            Err(error) => return Err(error),
        }
    }
    validate(&response)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn response(status: &str, body: &str) -> Vec<u8> {
        format!(
            "HTTP/1.1 {status}\r\nContent-Length: {}\r\n\r\n{body}",
            body.len()
        )
        .into_bytes()
    }

    #[test]
    fn maps_unspecified_addresses_without_changing_the_port() {
        for (input, expected) in [
            ("0.0.0.0:3417", "127.0.0.1:3417"),
            ("[::]:3418", "[::1]:3418"),
            ("127.0.0.1:3419", "127.0.0.1:3419"),
        ] {
            let expected: SocketAddr = expected.parse().unwrap();
            assert_eq!(target(input.parse().unwrap()).unwrap(), expected);
        }
        assert!(target("127.0.0.1:0".parse().unwrap()).is_err());
    }

    #[test]
    fn accepts_only_bounded_alive_metadata_with_a_success_status() {
        assert!(validate(&response("200 OK", r#"{"status":"alive"}"#)).is_ok());
        for (status, body) in [
            ("404 Not Found", "200 OK"),
            ("503 Unavailable", r#"{"status":"alive"}"#),
            ("200 OK", r#"{"status":"ready"}"#),
            ("200 OK", r#"{"status":"dead","status":"alive"}"#),
            ("200 OK", r#"{"status":"alive","extra":true}"#),
            ("200 OK", "not-json"),
            ("200 OK", r#"["alive"]"#),
            ("302 Redirect", r#"{"status":"alive"}"#),
        ] {
            assert!(validate(&response(status, body)).is_err());
        }
    }

    #[test]
    fn rejects_ambiguous_or_incomplete_http_framing() {
        for raw in [
            b"HTTP/1.1 200 OK\r\n\r\n{}".as_slice(),
            b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n{\"status\":\"alive\"}",
            b"HTTP/1.1 200 OK\r\nContent-Length: 18\r\nContent-Length: 18\r\n\r\n{\"status\":\"alive\"}",
            b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
            b"HTTP/1.1 200 OK\r\nContent-Length: 18\r\n\r\n{",
        ] {
            assert!(validate(raw).is_err());
        }
        assert!(validate(&vec![b'x'; LIMIT + 1]).is_err());
    }
}

"""Explicit localhost-only HTTPS test proxy. Never a production proxy/service."""
import argparse
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import ipaddress
import os
from pathlib import Path
import ssl

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from cryptography.x509.oid import ExtendedKeyUsageOID


def private_write(path, data):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / name for name in ("ca.key", "ca.crt", "localhost.key", "localhost.crt")]
    if all(path.exists() for path in paths):
        return
    if any(path.exists() for path in paths):
        raise SystemExit("Partial certificate set exists; inspect it rather than overwriting keys.")
    now = datetime.now(timezone.utc)
    root_key, leaf_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Netloom LOCAL TEST ONLY CA")])
    leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    root = (x509.CertificateBuilder().subject_name(root_name).issuer_name(root_name).public_key(root_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=30)).add_extension(x509.BasicConstraints(ca=True, path_length=0), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=None, decipher_only=None), True)
            .sign(root_key, hashes.SHA256()))
    leaf = (x509.CertificateBuilder().subject_name(leaf_name).issuer_name(root_name).public_key(leaf_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=7)).add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), False)
            .add_extension(x509.KeyUsage(digital_signature=True, key_encipherment=False, content_commitment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=None, decipher_only=None), True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(root_key, hashes.SHA256()))
    for path, key in ((paths[0], root_key), (paths[2], leaf_key)):
        private_write(path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for path, cert in ((paths[1], root), (paths[3], leaf)):
        private_write(path, cert.public_bytes(serialization.Encoding.PEM))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(".tools/production-staged/tls"))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--port", type=int, choices=(18210, 18220))
    parser.add_argument("--upstream-port", type=int, choices=(18150, 18160))
    args = parser.parse_args()
    directory = args.directory.resolve()
    prepare(directory)
    if args.prepare_only:
        print("Local test TLS files prepared; no system trust store or runtime settings changed.")
        return
    if (args.port, args.upstream_port) not in ((18210, 18160), (18220, 18150)):
        parser.error("Only isolated CAF18210->18160 and Radius18220->18150 pairs are allowed")

    class Proxy(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass  # Never print paths, cookies, authorization or customer data.

        def forward(self):
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if size < 0 or size > 32 * 1024 * 1024 or self.headers.get("Transfer-Encoding") or not self.path.startswith("/") or self.path.startswith("//"):
                self.send_error(400)
                return
            hop = {"host", "connection", "transfer-encoding", "keep-alive", "proxy-authorization", "proxy-authenticate", "upgrade", "te", "trailer"}
            headers = {key: value for key, value in self.headers.items() if key.lower() not in hop and not key.lower().startswith("x-forwarded-")}
            headers.update({"Host": f"127.0.0.1:{args.port}", "X-Forwarded-Proto": "https", "X-Forwarded-Host": f"127.0.0.1:{args.port}"})
            upstream = http.client.HTTPConnection("127.0.0.1", args.upstream_port, timeout=60)
            try:
                upstream.request(self.command, self.path, body=self.rfile.read(size) if size else None, headers=headers)
                result = upstream.getresponse()
                body = result.read(40 * 1024 * 1024 + 1)
                if len(body) > 40 * 1024 * 1024:
                    raise ValueError
                self.send_response(result.status)
                for key, value in result.getheaders():
                    if key.lower() not in hop | {"content-length"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
            except (OSError, ValueError, http.client.HTTPException):
                self.send_error(502, "Isolated local upstream unavailable")
            finally:
                upstream.close()

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_HEAD = forward

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Proxy)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(directory / "localhost.crt", directory / "localhost.key")
    server.socket = context.wrap_socket(server.socket, server_side=True)
    print(f"Local test HTTPS127.0.0.1:{args.port} -> isolated loopback{args.upstream_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

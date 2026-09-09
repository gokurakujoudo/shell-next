#!/usr/bin/env bash
set -euo pipefail

# Runs only in the disposable RHEL 8 UBI CI container.
dnf install -y gcc make openssl-devel libffi-devel zlib-devel bzip2-devel xz-devel \
  sqlite-devel curl tar gzip findutils shadow-utils sudo git
if [[ ! -x /opt/python/bin/python3.14 ]]; then
  curl --fail --location --retry 3 https://www.python.org/ftp/python/3.14.2/Python-3.14.2.tgz -o /tmp/python.tgz
  tar -xzf /tmp/python.tgz -C /tmp
  cd /tmp/Python-3.14.2
  ./configure --prefix=/opt/python --with-ensurepip=install --disable-test-modules
  make -j2
  make install
fi

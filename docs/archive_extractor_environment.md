# Archive Extractor Environment

## Installation

`unar`/`lsar` were not installed at the start of this stage
(`command -v unar` / `command -v lsar` both returned not-found; `apt-cache
policy unar` showed candidate `1.10.7+ds1+really1.10.1-3build1`, not
installed).

**`sudo apt update && sudo apt install -y unar` requires an interactive
password.** The automated tool session has no TTY to supply one, and per the
project's safety rules this was not bypassed. The user was asked to either
run the install themselves or cache `sudo` credentials via `sudo -v` in their
own terminal. The user ran the install (or an equivalent action) outside this
session; `unar`/`lsar` were confirmed present immediately afterward.

`unrar` was **not** installed — `unar` extraction succeeded (see
`docs/dejavu_extraction_report.md`), so the "only install `unrar` if `unar`
demonstrably fails" condition was never triggered.

## Recorded versions

```
$ unar --version
v1.10.1

$ lsar --version
v1.10.1

$ dpkg -s unar
Package: unar
Status: install ok installed
Version: 1.10.7+ds1+really1.10.1-3build1
Depends: gnustep-base-runtime (>= 1.29.0), libbz2-1.0, libc6 (>= 2.38),
  libgcc-s1 (>= 3.0), libgnustep-base1.29 (>= 1.29.0), libicu74 (>= 74.1-1~),
  libobjc4 (>= 4.2.1), libstdc++6 (>= 5), libwavpack1 (>= 4.40.0),
  zlib1g (>= 1:1.2.0)
```

`unar`/`lsar` are DFSG-compatible (free) and support RAR/RAR5 decompression,
unlike the `7zip+dfsg` build already on this machine, which can only list
RAR/RAR5 archives.

## Outcome

**Unar installation: INSTALLED** (previously absent, now present at
`/usr/bin/unar` and `/usr/bin/lsar`).

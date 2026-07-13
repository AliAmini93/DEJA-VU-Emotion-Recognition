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

**Original statement in this document (now superseded, see dated correction
below):** "`unrar` was not installed — `unar` extraction succeeded... so the
fallback condition was never triggered." This was true only up to the point
in that same continuation session where it was written. Later in that
session, `unar`'s extraction of the main archive was found to have
**deterministically truncated 39 of 308 files** (see
`docs/dejavu_extraction_report.md`) — exactly the "unar demonstrably fails"
condition this document originally said had never occurred. At that point
the user was asked whether to install `unrar` as a targeted fallback.

## Recorded versions (from that stage)

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

## Outcome (as of that stage)

**Unar installation: INSTALLED** (previously absent, now present at
`/usr/bin/unar` and `/usr/bin/lsar`).

---

## 2026-07-13 (this continuation stage) — `unrar` confirmed installed; prior session's gap corrected

**Correction, dated, not a silent rewrite (rule #12):** the user installed
`unrar` following the request described above, but the prior session ended
**before the archive was actually retried with `unrar`** — the 39-file
truncation blocker was left open despite the fix tool already being present.
This section corrects that gap: the 39-file blocker was, by the end of the
prior session, an **incomplete workflow** (the fix was installed but not
run), not a **missing package** as some of the prior session's summary
language implied.

Verified this stage:

```
$ command -v unrar
/usr/bin/unrar

$ unrar
UNRAR 7.00 freeware      Copyright (c) 1993-2024 Alexander Roshal

$ dpkg -s unrar
Package: unrar
Status: install ok installed
Version: 1:7.0.7-1build1
Section: non-free/utils
Depends: libc6 (>= 2.38), libgcc-s1 (>= 3.3.1), libstdc++6 (>= 11)
Homepage: https://www.rarlab.com/
```

`unrar` 7.00 is RARLAB's own official (non-free) reference implementation of
the RAR/RAR5 format — the canonical decoder, not a reverse-engineered
reimplementation like `unar`. See `docs/dejavu_unrar_validation_report.md`
for the outcome of retrying extraction with it.

## Outcome (current)

**Unar installation: INSTALLED** (from the prior stage).
**Unrar installation: INSTALLED** (`1:7.0.7-1build1`, confirmed this stage;
archive MD5 reverified unchanged — `0815b7d78915d132084f4ef497cef6d0` —
before any extraction was attempted).

# EasyNAS Immutable-OS / Image-Update Design

Status: **Proposed**
Author: Yariv Hakim

This document describes how EasyNAS moves from a single mutable install to an
**immutable-OS appliance** where:

1. **Full install** (from the ISO) rewrites *everything*, including settings — a clean slate.
2. **Upgrade** replaces *only the OS part*, preserving user settings and data.
3. The OS part is published and fetched **over the internet**.

---

## 1. The three layers

The whole design rests on splitting the system into three independent layers.
Updates only ever touch Layer 1.

| Layer | Contents | Mutability | Touched by upgrade? |
|------|----------|-----------|---------------------|
| **1. OS image** | base OS + `/easynas` app code + static units/config | read-only, replaceable | **Yes — replaced** |
| **2. Config** | user/group accounts, certs, `/etc/easynas`, fstab entries for data, NetworkManager profiles, cron | read-write, persistent | No |
| **3. Data** | the user's btrfs NAS pools, subvolumes, snapshots | read-write, on separate disks | No |

---

## 2. Disk layout

```
SYSTEM DISK
 ├─ ESP (EFI)         bootloader + active-slot pointer
 ├─ root-A   (ro)  ┐  OS image slot  (incl. /easynas app code)
 ├─ root-B   (ro)  ┘  inactive slot receives upgrades
 └─ config   (rw)     persistent settings (Layer 2)

DATA DISKS (separate)
 └─ btrfs NAS pools (Layer 3) — never touched by install or upgrade
```

With `transactional-update` (recommended, see §4) the A/B slots are btrfs
read-only **snapshots** rather than fixed partitions, and `config` is a
persistent subvolume excluded from snapshots.

---

## 3. The two flows

### Full install (from ISO) — rewrites everything
1. Partition the system disk.
2. Write the OS image to root-A.
3. **Format `config` and seed it with factory defaults** → settings wiped.
4. Install bootloader pointing at root-A.

### Upgrade (over the internet) — OS only
1. Fetch the new OS from `repo.easynas.org`.
2. Apply it into the **inactive** slot (root-B / new snapshot).
3. Flip the boot pointer; reboot.
4. `config` and data disks are never written → settings + data survive.
5. If the new slot fails to boot → automatic rollback to the previous slot.

---

## 4. Implementation paths

### Path A — `transactional-update` + read-only btrfs root  *(recommended)*
- Native to openSUSE; **reuses the existing KIWI build, RPM repo, and firmware module**.
- The "OS image" is a read-only btrfs snapshot; `transactional-update dup`
  pulls from the existing zypper repo into a new snapshot and reboots into it.
- Rollback via snapper + GRUB.
- Lowest new infrastructure; the "OS over the internet" is just the current repo.

### Path B — RAUC + true A/B partition images
- Industry-standard image-based updates: signed bundles, bootloader-integrated,
  atomic, auto-rollback.
- Requires building/hosting full slot images and integrating RAUC into GRUB.
- Reserve for when signed image bundles are wanted.

**Decision: Path A**, because it meets all three requirements with the least
new machinery and keeps the RPM/KIWI pipeline intact.

---

## 5. Runtime path inventory (what goes where)

### Layer 1 — OS image (read-only)
- `/easynas/**` (lib, templates, public, script, startup, addons, lang)
- `/usr/lib/systemd/system/easynas.service` *(see Conflict #1)*
- `/usr/lib/systemd/system/easynas-sshd.service`
- `/etc/sudoers.d/easynas`
- `/etc/zypp/repos.d/*.repo`
- `/etc/easynas/sshd_config`

### Layer 2 — config (persistent, read-write)
| Path | Written by |
|------|-----------|
| `/etc/fstab` (data-pool mounts) | `filesystem.pm` |
| `/etc/passwd`, `/etc/shadow`, `/etc/group` | `users.pm`, `groups.pm` |
| `/var/lib/samba/` passdb | `users.pm` (smbpasswd) |
| `/etc/easynas/easynas.cert`, `.key` | first-boot service *(see Conflict #3)* |
| `/etc/easynas/easynas.lang` | `easynas.pm` |
| `/etc/easynas/easynas.updates` | `firmware.pm` |
| `/etc/easynas/addons/*.addon`, `easynas.addons` | `addons.pm` |
| `/etc/hostname`, `/etc/hosts` | `settings.pm` |
| `/etc/NetworkManager/system-connections/` | `network.pm` |
| `/etc/cron.d/easynas.cron` | `filesystem.pm`, `volume.pm` *(see Conflict #2)* |
| `/var/log/easynas/easynas.log` | `write_log` |

### Layer 3 — data (separate disks)
- `/mnt/<fs>` btrfs pools + subvolumes/snapshots (managed by `volume.pm`).

---

## 6. Conflicts to fix (code writes into would-be read-only Layer 1)

These block immutability and must be fixed first. They are independent of the
chosen swap mechanism.

1. **Port change edits the systemd unit in place.**
   `settings.pm` does `sed -i` on `/usr/lib/systemd/system/easynas.service`.
   → Move the port to a writable **drop-in**
   (`/etc/systemd/system/easynas.service.d/override.conf`) or an
   `EnvironmentFile` in `/etc/easynas`, and edit *that*.

2. **Cron file is both shipped and runtime-mutated.**
   Installed by the RPM but `sed`-edited by `filesystem.pm` / `volume.pm`.
   → Must live entirely on the `config` layer, seeded once at first boot.

3. **SSL cert generated in RPM `%post`.**
   In an image model `%post` runs at build time → every appliance ships the
   same key, or it regenerates on every update.
   → Generate via a **first-boot service** that writes to persistent
   `/etc/easynas/` only if the cert is absent.

---

## 7. Factory reset

`startup/easynas.sh` currently runs `tar -xf settings.tar -C /`.
In the immutable model, factory reset = **reset the `config` layer to defaults**
(or roll to the base snapshot), leaving Layer 1 and Layer 3 untouched.

---

## 8. KIWI implementation — separate config partition (chosen approach)

Decision: a **separate persistent `config` partition** on the system disk
(not full read-only/transactional root). Upgrade replaces the root; `config`
and the data disks are left untouched.

### 8.1 Partition mechanism

Add a spare partition to each x86_64 profile via `oemconfig`:

```xml
<oemconfig>
    ...
    <spare_part mountpoint="/etc/easynas">512</spare_part>
</oemconfig>
```

KIWI creates one extra partition on the install target and mounts it at the
given path (recorded in `/etc/fstab` of the installed system).

### 8.2 The mount-shadowing problem

`/etc/easynas` currently holds a mix:

| File | Layer | Action |
|------|-------|--------|
| `easynas.conf`, `easynas.lang`, `easynas.updates`, `easynas.cert/key`, `addons/*.addon`, `addons/easynas.addons` | config | belong on the partition — seed via firstboot |
| `sshd_config` | **image (static)** | mounting the partition over `/etc/easynas` would **shadow** it → SSH breaks |

So before mounting `config` at `/etc/easynas`, the static `sshd_config` must
move out (e.g. to `/easynas/conf/sshd_config`, referenced by the
`easynas-sshd.service` `ExecStart`). After that, `/etc/easynas` is purely
config-layer and safe to back with the partition. `firstboot.sh` already seeds
the config files if absent.

### 8.3 Layer 2 that lives outside /etc/easynas

A single partition at `/etc/easynas` does **not** capture the rest of Layer 2:

- `/etc/passwd`, `/etc/shadow`, `/etc/group` — NAS accounts (needed very early at boot)
- `/etc/fstab` — data-pool mounts
- `/etc/hostname`, `/etc/hosts`
- `/etc/NetworkManager/system-connections/`
- `/var/lib/samba/` — SMB passdb

Strategy: store these under the `config` partition (e.g.
`/etc/easynas/persist/...`) and **bind-mount** each onto its real location via
early-ordered `systemd` mount/`.conf` units, before the consumers start.

> **Open decision — system accounts.** `/etc/passwd` & `/etc/shadow` are read
> extremely early. Bind-mounting them from `config` works but is fragile.
> Longer term, moving NAS users into a dedicated user DB on `config` (and out
> of the system files) is cleaner. Pick one before implementing 8.3.

### 8.4 Caveat — what "survives an upgrade" requires

KIWI's OEM install-from-ISO **repartitions the whole disk**, which would wipe
`config`. So "upgrade replaces OS only, settings survive" only holds if the
**upgrade is in-place** (zypper/RPM from the repo, or an A/B root swap) — *not*
a fresh OEM reinstall from the ISO. The ISO is for full (wipe-everything)
installs (requirement #1); the online OS update path must be in-place
(requirement #2/#3).

### 8.5 Validation (must run on a real build)

1. Build the ISO; install to a VM.
2. Set a custom port, create a NAS user, create a filesystem.
3. Apply an in-place OS update from the repo.
4. Confirm port, user, and fstab/data mounts all survived.

---

## 9. Addon persistence across upgrades

Addons (`easynas-fs-ssh`, `easynas-fs-samba`, `easynas-mm-plex`, …) are optional
RPMs the user installs *after* the base image is built. They drop files into the
**OS tree** (`/easynas/lib`, `/easynas/templates`, `/easynas/lang`,
`/easynas/addons`, `/usr/lib/systemd/system`) as well as config
(`/etc/easynas/...`). Because they live in the OS part, whether they survive an
upgrade depends entirely on **how the upgrade applies**.

### 9.1 The deciding fork

| Upgrade mechanism | What happens to addons |
|-------------------|------------------------|
| **In-place** (`zypper` / `transactional-update dup` from the repo) | Addons are packages that **carry forward** — base + addons update together. **No special home needed.** Only their *config* lives on the config partition. |
| **Image swap / re-flash** (new root image replaces old) | The new image lacks the post-install addon RPMs → they **vanish**. Must be preserved + re-applied. |

### 9.2 Recommendation — in-place updates

Make the online OS update an **in-place `transactional-update dup`** from
`repo.easynas.org`, and treat "replace the OS" as new-snapshot semantics rather
than a literal wipe. Then addon persistence is automatic: addons are RPMs that
update alongside the base, and the only addon state on the config partition is
their config files (`sshd_config`, samba shares, etc.), already handled by §8.

This is the chosen approach — it reuses the existing RPM repo and needs no extra
machinery for addons.

### 9.3 Fallback for literal image-swap

If a literal image-swap upgrade is ever adopted, addons must be preserved on a
**persistent partition** (config partition or a dedicated `addons` subvolume),
re-applied one of two ways:

1. **Record + reinstall (preferred).** The installed-addon list already exists
   as `/etc/easynas/addons/easynas.addons` (config layer). A first-boot step
   after a swap runs `zypper install` for each recorded addon from the repo, so
   addons always match the new OS version. Needs network at upgrade; brief gap
   until reinstalled.
2. **systemd-sysext overlay.** Ship each addon as a versioned sysext extension
   image in `/var/lib/extensions` on the persistent partition; systemd merges it
   read-only into `/usr` (extended to `/easynas`) at boot. Survives swaps with no
   reinstall, works offline. Cost: addons must be built as sysext images
   (`extension-release` versioned), not plain RPMs.

### 9.4 Net answer to "where do addons go?"

- **Config** (sshd_config, shares, etc.) → config partition (already planned).
- **Code / RPMs** → no separate home needed under in-place updates (§9.2); or
  recorded on the config partition and reinstalled (§9.3.1), or as sysext images
  on the persistent partition (§9.3.2) under image-swap.

---

## 10. Task checklist

- [x] Fix Conflict #1 — listen port off the systemd unit (`easynas.conf`).
- [x] Fix Conflict #2 — cron seeded on the config layer at first boot.
- [x] Fix Conflict #3 — cert generation via first-boot service.
- [x] Relocate static `sshd_config` out of `/etc/easynas` → `/easynas/conf` (§8.2).
- [ ] Decide system-accounts strategy (§8.3 open decision).
- [ ] KIWI: add `spare_part` config partition to the x86_64 profiles (§8.1).
- [ ] Bind-mount the scattered Layer 2 paths from `config` (§8.3).
- [ ] Adopt in-place `transactional-update dup` for online OS updates (§8.4, §9.2).
- [ ] Rework factory reset to reset the `config` partition.
- [ ] Validate on a real build (§8.5).

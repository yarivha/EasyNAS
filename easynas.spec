Name:           easynas
Version:        1.99
Release:        1
Summary:        Network Attached Storage
License:        GPL-3.0
Group:          System Environment/Daemons
URL:            https://www.easynas.org
BuildArch:      noarch
Source0:        %{name}-%{version}.tar.gz

Requires:       perl
Requires:       perl-Mojolicious
Requires:       perl-XML-LibXML
Requires:       perl-IO-Socket-SSL
Requires:       btrfsprogs
Requires:       cron
Requires:       hdparm
Requires:       smartmontools
Requires:       net-snmp
Requires:       openssl
Requires:       sudo
Requires:       tar
Requires:       rsync
Requires:       NetworkManager
Requires:       dmidecode

%description
EasyNAS is a Network Attached Storage Server.

%prep
%setup -q

%install
mkdir -p %{buildroot}/easynas
mkdir -p %{buildroot}/etc/easynas/addons
mkdir -p %{buildroot}/etc/cron.d
mkdir -p %{buildroot}/etc/sudoers.d
mkdir -p %{buildroot}/etc/zypp/repos.d
mkdir -p %{buildroot}/var/log/easynas
mkdir -p %{buildroot}/usr/lib/systemd/system

cp -a addons lib templates public script startup lang t %{buildroot}/easynas/
cp easy_n_a_s.yml %{buildroot}/easynas/

cat > %{buildroot}/etc/sudoers.d/easynas << 'EOF'
easynas ALL = NOPASSWD: ALL
admin   ALL = NOPASSWD: ALL
EOF
chmod 440 %{buildroot}/etc/sudoers.d/easynas

# /etc/cron.d/easynas.cron is no longer shipped in the image; it is seeded on
# the writable config layer by the firstboot service (see startup/firstboot.sh)
# because the app rewrites it at runtime.

echo "en-en" > %{buildroot}/etc/easynas/easynas.lang

cat > %{buildroot}/etc/easynas/addons/easynas.addons << 'EOF'
<?xml version='1.0'?>
<stream>
<search-result version="0.0">
<solvable-list>
<solvable status="installed" name="easynas" summary="Network Attached Storage" kind="package"/>
<solvable status="not-installed" name="easynas-fs-afp" summary="AFP addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-ftp" summary="FTP addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-nfs" summary="NFS addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-rsyncd" summary="RSyncd addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-samba" summary="SAMBA addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-ssh" summary="SSH addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-fs-tftp" summary="TFTP addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-lang-chinese" summary="Simplified Chinese Language for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-lang-german" summary="German Language for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-lang-polish" summary="Polish Language for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-lang-portuguese" summary="Portuguese Language for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-mm-dlna" summary="DLNA addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-mm-plex" summary="PLEX addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-srv-radius" summary="Radius addon for EasyNAS" kind="package"/>
<solvable status="not-installed" name="easynas-stg-iscsi" summary="iSCSI Initiator addon for EasyNAS" kind="package"/>
</solvable-list>
</search-result>
</stream>
EOF

cat > %{buildroot}/etc/zypp/repos.d/EasyNAS.repo << 'EOF'
[EasyNAS]
enabled=1
autorefresh=1
baseurl=https://repo.easynas.org/easynas2/RPMS/
type=rpm-md
gpgcheck=1
gpgkey=https://repo.easynas.org/EASYNAS-GPG-KEY.gpg
keeppackages=0
EOF

cat > %{buildroot}/etc/zypp/repos.d/EasyNAS_Beta.repo << 'EOF'
[EasyNAS_Beta]
enabled=0
autorefresh=1
baseurl=https://repo.easynas.org/testing/RPMS/
type=rpm-md
gpgcheck=1
gpgkey=https://repo.easynas.org/EASYNAS-GPG-KEY.gpg
keeppackages=0
EOF

cat > %{buildroot}/usr/lib/systemd/system/easynas.service << 'EOF'
[Unit]
Description=EasyNAS application
After=network.target

[Service]
Type=simple
User=easynas
Environment=EASYNAS_PORT=1443
EnvironmentFile=-/etc/easynas/easynas.conf
ExecStart=/easynas/script/easy_nas daemon -m production -l https://*:${EASYNAS_PORT}?cert=/etc/easynas/easynas.cert&key=/etc/easynas/easynas.key

[Install]
WantedBy=multi-user.target
EOF

cat > %{buildroot}/usr/lib/systemd/system/easynas-firstboot.service << 'EOF'
[Unit]
Description=EasyNAS first-boot config seeding
After=local-fs.target
Before=easynas.service

[Service]
Type=oneshot
ExecStart=/easynas/startup/firstboot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Persistent settings file (config layer). Seeded only if absent so an
# upgrade never overwrites a user-chosen port; see %post.
echo "EASYNAS_PORT=1443" > %{buildroot}/etc/easynas/easynas.conf

touch %{buildroot}/var/log/easynas/easynas.log

# ImageVersion identifies the OS build and is read from /etc/ImageVersion by
# easynas.pm; it lives on the image (updates with the OS), not the config layer.
mkdir -p %{buildroot}/etc
echo "EasyNAS-%{version}" > %{buildroot}/etc/ImageVersion

# SSH subpackage files.
# sshd_config is a static addon file and lives on the OS image under
# /easynas/conf, NOT /etc/easynas -- the config partition mounts over
# /etc/easynas and would otherwise shadow it (see docs/immutable-design.md 8.2).
mkdir -p %{buildroot}/easynas/conf
cat > %{buildroot}/easynas/conf/sshd_config << 'EOF'
AuthorizedKeysFile	.ssh/authorized_keys
UsePAM yes
X11Forwarding yes
Subsystem	sftp	/usr/lib/ssh/sftp-server
AcceptEnv LANG LC_CTYPE LC_NUMERIC LC_TIME LC_COLLATE LC_MONETARY LC_MESSAGES
AcceptEnv LC_PAPER LC_NAME LC_ADDRESS LC_TELEPHONE LC_MEASUREMENT
AcceptEnv LC_IDENTIFICATION LC_ALL
EOF

cat > %{buildroot}/usr/lib/systemd/system/easynas-sshd.service << 'EOF'
[Unit]
Description=OpenSSH Daemon
After=network.target

[Service]
Type=notify
EnvironmentFile=-/etc/sysconfig/ssh
ExecStartPre=/usr/sbin/sshd-gen-keys-start
ExecStartPre=/usr/sbin/sshd -t $SSHD_OPTS
ExecStart=/usr/sbin/sshd -f /easynas/conf/sshd_config  -D $SSHD_OPTS
ExecReload=/bin/kill -HUP $MAINPID
KillMode=process
Restart=always
TasksMax=infinity

[Install]
WantedBy=multi-user.target
EOF


%files
%config(noreplace) /etc/easynas/easynas.lang
%config(noreplace) /etc/easynas/easynas.conf
%config(noreplace) /etc/easynas/addons/easynas.addons
%config(noreplace) /var/log/easynas/easynas.log
/etc/zypp/repos.d
/etc/sudoers.d/easynas
/etc/ImageVersion
/usr/lib/systemd/system/easynas.service
/usr/lib/systemd/system/easynas-firstboot.service
/easynas/easy_n_a_s.yml
/easynas/script
/easynas/public
/easynas/t
/easynas/addons/dashboard.easynas
/easynas/addons/addons.easynas
/easynas/addons/backup.easynas
/easynas/addons/disk.easynas
/easynas/addons/filesystem.easynas
/easynas/addons/groups.easynas
/easynas/addons/network.easynas
/easynas/addons/profile.easynas
/easynas/addons/scheduler.easynas
/easynas/addons/users.easynas
/easynas/addons/volume.easynas
/easynas/addons/sync.easynas
/easynas/addons/firmware.easynas
/easynas/addons/power.easynas
/easynas/addons/settings.easynas
/easynas/addons/computers.easynas
/easynas/addons/realm.easynas
/easynas/lib/EasyNAS.pm
/easynas/lib/EasyNAS/Controller/disk.pm
/easynas/lib/EasyNAS/Controller/easynas.pm
/easynas/lib/EasyNAS/Controller/filesystem.pm
/easynas/lib/EasyNAS/Controller/volume.pm
/easynas/lib/EasyNAS/Controller/dashboard.pm
/easynas/lib/EasyNAS/Controller/login.pm
/easynas/lib/EasyNAS/Controller/addons.pm
/easynas/lib/EasyNAS/Controller/users.pm
/easynas/lib/EasyNAS/Controller/groups.pm
/easynas/lib/EasyNAS/Controller/firmware.pm
/easynas/lib/EasyNAS/Controller/network.pm
/easynas/lib/EasyNAS/Controller/settings.pm
/easynas/templates/layouts
/easynas/templates/easynas/disk*
/easynas/templates/easynas/filesystem*
/easynas/templates/easynas/volume*
/easynas/templates/easynas/dashboard*
/easynas/templates/easynas/settings*
/easynas/templates/easynas/addons*
/easynas/templates/easynas/users*
/easynas/templates/easynas/groups*
/easynas/templates/easynas/network*
/easynas/templates/easynas/firmware*
/easynas/templates/easynas/login*
/easynas/startup
/easynas/lang/en-en/iso.txt
/easynas/lang/en-en/lang_english_easynas.pl


%pre
/usr/bin/getent group easynas || /usr/sbin/groupadd -r easynas
/usr/bin/getent passwd easynas || /usr/sbin/useradd -r -g easynas -d /easynas -s /sbin/nologin easynas


%post
systemctl enable easynas.service easynas-firstboot.service

# On a live system, seed the config layer (cert, port, cron) and restart now.
# During an image build there is no running systemd, so this is skipped and the
# enabled firstboot service seeds at the first real boot instead -- which keeps
# the SSL cert out of the image so every appliance gets its own (conflict #3).
if [ -d /run/systemd/system ]; then
    /easynas/startup/firstboot.sh
    systemctl daemon-reload
    systemctl restart easynas.service
fi


%postun


%clean


#### lxc ####
%package        srv-lxc
Version:        %{version}
Summary:        Virtualization addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       lxc
Requires:       ttyd
Requires:       libwebsockets-devel

%description srv-lxc
Virtualization addon for EasyNAS

%files srv-lxc
/easynas/addons/lxc.easynas
/easynas/lib/EasyNAS/Controller/lxc.pm
/easynas/lang/en-en/lang_english_lxc.pl
/easynas/templates/easynas/lxc.html.ep
/easynas/templates/easynas/lxc_create.html.ep


#### mariadb ####
%package        srv-mariadb
Version:        %{version}
Summary:        MariaDB addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}

%description srv-mariadb
MariaDB addon for EasyNAS

%files srv-mariadb
/easynas/addons/mariadb.easynas
/easynas/lang/en-en/lang_english_mariadb.pl


##### TFTP #####
%package        fs-tftp
Version:        %{version}
Summary:        TFTP addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       tftp

%description fs-tftp
TFTP addon for EasyNAS

%files fs-tftp
/easynas/addons/tftp.easynas
/easynas/lang/en-en/lang_english_tftp.pl
/easynas/lang/de-de/lang_german_tftp.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_tftp.pl
/easynas/lang/zh-cn/lang_chinese_tftp.pl
/easynas/lang/pl-pl/lang_polish_tftp.pl


##### AFP ####
%package        fs-afp
Version:        %{version}
Summary:        AFP addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       netatalk

%description fs-afp
AFP addon for EasyNAS

%files fs-afp
/easynas/addons/afp.easynas
/easynas/lang/en-en/lang_english_afp.pl
/easynas/lang/de-de/lang_german_afp.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_afp.pl
/easynas/lang/zh-cn/lang_chinese_afp.pl
/easynas/lang/pl-pl/lang_polish_afp.pl


##### FTP ####
%package        fs-ftp
Version:        %{version}
Summary:        FTP addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       pureftpd

%description fs-ftp
FTP addon for EasyNAS

%files fs-ftp
/easynas/addons/ftp.easynas
/easynas/lang/en-en/lang_english_ftp.pl
/easynas/lang/de-de/lang_german_ftp.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_ftp.pl
/easynas/lang/zh-cn/lang_chinese_ftp.pl
/easynas/lang/pl-pl/lang_polish_ftp.pl


##### NFS ####
%package        fs-nfs
Version:        %{version}
Summary:        NFS addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       nfs-kernel-server

%description fs-nfs
NFS addon for EasyNAS

%files fs-nfs
/easynas/addons/nfs.easynas
/easynas/lib/EasyNAS/Controller/nfs.pm
/easynas/templates/easynas/nfs.html.ep
/easynas/templates/easynas/nfs_create.html.ep
/easynas/lang/en-en/lang_english_nfs.pl
/easynas/lang/de-de/lang_german_nfs.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_nfs.pl
/easynas/lang/zh-cn/lang_chinese_nfs.pl
/easynas/lang/pl-pl/lang_polish_nfs.pl


##### SAMBA ####
%package        fs-samba
Version:        %{version}
Summary:        SAMBA addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       samba
Requires:       samba-winbind
Requires:       rpcbind

%description fs-samba
SAMBA addon for EasyNAS

%files fs-samba
/easynas/addons/samba.easynas
/easynas/lang/en-en/lang_english_samba.pl
/easynas/lang/de-de/lang_german_samba.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_samba.pl
/easynas/lang/zh-cn/lang_chinese_samba.pl
/easynas/lang/pl-pl/lang_polish_samba.pl


##### SSH ####
%package        fs-ssh
Version:        %{version}
Summary:        SSH addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       openssh

%description fs-ssh
SSH addon for EasyNAS

%files fs-ssh
/easynas/addons/ssh.easynas
/easynas/lib/EasyNAS/Controller/ssh.pm
/easynas/templates/easynas/ssh*
/easynas/lang/en-en/lang_english_ssh.pl
/easynas/conf/sshd_config
/usr/lib/systemd/system/easynas-sshd.service


#### DLNA ####
%package        mm-dlna
Version:        %{version}
Summary:        DLNA addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       minidlna
Requires:       ffmpeg

%description mm-dlna
DLNA addon for EasyNAS

%files mm-dlna
/easynas/addons/dlna.easynas
/easynas/lang/en-en/lang_english_dlna.pl
/easynas/lang/de-de/lang_german_dlna.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_dlna.pl
/easynas/lang/zh-cn/lang_chinese_dlna.pl
/easynas/lang/pl-pl/lang_polish_dlna.pl


#### Plex ####
%package        mm-plex
Version:        %{version}
Summary:        PLEX addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       plexmediaserver

%description mm-plex
Plex Server addon for EasyNAS

%files mm-plex
/easynas/addons/plex.easynas
/easynas/lang/en-en/lang_english_plex.pl
/easynas/lang/pl-pl/lang_polish_plex.pl


#### RSync ####
%package        fs-rsyncd
Version:        %{version}
Summary:        RSyncd addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       rsync

%description fs-rsyncd
RSyncd addon for EasyNAS

%files fs-rsyncd
/easynas/addons/rsyncd.easynas
/easynas/lang/en-en/lang_english_rsync.pl
/easynas/lang/de-de/lang_german_rsync.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_rsync.pl
/easynas/lang/zh-cn/lang_chinese_rsync.pl
/easynas/lang/pl-pl/lang_polish_rsync.pl


#### Radius ####
%package        srv-radius
Version:        %{version}
Summary:        Radius addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       freeradius-server

%description srv-radius
Radius addon for EasyNAS

%files srv-radius
/easynas/addons/radius.easynas
/easynas/lang/en-en/lang_english_radius.pl
/easynas/lang/de-de/lang_german_radius.pl
/easynas/lang/pt-br/lang_brazilian_portuguese_radius.pl
/easynas/lang/zh-cn/lang_chinese_radius.pl
/easynas/lang/pl-pl/lang_polish_radius.pl


#### iSCSI ####
%package        stg-iscsi
Version:        %{version}
Summary:        iSCSI Initiator addon for EasyNAS
Group:          easynas/addon
Requires:       easynas >= %{version}
Requires:       tgt

%description stg-iscsi
iSCSI addon for EasyNAS

%files stg-iscsi
/easynas/addons/iscsi.easynas
/easynas/lang/en-en/lang_english_iscsi.pl
/easynas/lang/pl-pl/lang_polish_iscsi.pl


##### German Language ####
%package        lang-german
Version:        %{version}
Summary:        German Language for EasyNAS
Group:          easynas/lang
Requires:       easynas >= %{version}

%description lang-german
German Language for EasyNAS

%files lang-german
/easynas/lang/de-de/iso.txt
/easynas/lang/de-de/lang_german_easynas.pl


##### Portuguese Language ####
%package        lang-portuguese
Version:        %{version}
Summary:        Portuguese Language for EasyNAS
Group:          easynas/lang
Requires:       easynas >= %{version}

%description lang-portuguese
Portuguese Language for EasyNAS

%files lang-portuguese
/easynas/lang/pt-br/iso.txt
/easynas/lang/pt-br/lang_brazilian_portuguese_easynas.pl


##### Chinese Language ####
%package        lang-chinese
Version:        %{version}
Summary:        Simplified Chinese Language for EasyNAS
Group:          easynas/lang
Requires:       easynas >= %{version}

%description lang-chinese
Simplified Chinese Language for EasyNAS

%files lang-chinese
/easynas/lang/zh-cn/iso.txt
/easynas/lang/zh-cn/lang_chinese_easynas.pl


##### Polish Language ####
%package        lang-polish
Version:        %{version}
Summary:        Polish Language for EasyNAS
Group:          easynas/lang
Requires:       easynas >= %{version}

%description lang-polish
Polish Language for EasyNAS

%files lang-polish
/easynas/lang/pl-pl/iso.txt
/easynas/lang/pl-pl/lang_polish_easynas.pl


%changelog
* Thu Jun 26 2026 Yariv Hakim
  - Restructure repo, add CI build via GitHub Actions
* Wed Apr 10 2024 Yariv
  - First Release (R1)

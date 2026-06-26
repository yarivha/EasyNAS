#!/bin/bash
#
# firstboot.sh
#
# Seeds EasyNAS persistent config-layer state (/etc/easynas, cron) if it is
# absent, then fixes ownership. Idempotent: every operation is guarded by an
# "if missing" check, so it is safe to run on every boot and self-heals after
# a factory reset of the config layer.
#
# In the immutable-OS model the OS image is read-only; this script is what
# populates the writable config layer on first boot instead of doing it at
# RPM build time. See docs/immutable-design.md.
#
# This file is part of EasyNAS (c) created by Yariv Hakim 2012-2017
#

CONF_DIR=/etc/easynas
CRON=/etc/cron.d/easynas.cron

# SSL certificate (conflict #3): generate only if missing, so an OS upgrade
# never regenerates the appliance's identity.
if [ ! -f ${CONF_DIR}/easynas.cert ]; then
    openssl req -x509 -newkey rsa:2048 \
        -keyout ${CONF_DIR}/easynas.key \
        -out ${CONF_DIR}/easynas.cert \
        -sha256 -days 365 -nodes \
        -subj "/C=US/ST=Oregon/O=EasyNAS/OU=Org/CN=easynas"
fi

# Listen port (conflict #1): seed the default if missing.
if [ ! -f ${CONF_DIR}/easynas.conf ]; then
    echo "EASYNAS_PORT=1443" > ${CONF_DIR}/easynas.conf
fi

# Cron schedule (conflict #2): seed the default update-check entry if missing.
# Per-filesystem scrub and snapshot entries are appended/removed at runtime by
# the application, which is why the file must live on the writable config layer.
if [ ! -f ${CRON} ]; then
    echo '0 */6 * * *  root sleep ${RANDOM:0:2}m ;/easynas/startup/check_update.pl' > ${CRON}
fi

chown -R easynas:easynas ${CONF_DIR}
chown -R easynas:easynas /var/log/easynas

exit 0

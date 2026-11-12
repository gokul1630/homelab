#!/bin/bash

set -eux

apk update && \
apk upgrade && \
apk add gawk coreutils-sort \
		luci sed adblock-fast \
		grep luci-app-adblock-fast

cat >> /usr/bin/internet_led_watchdog.sh <<'EOF'
TARGET="8.8.8.8"

RED_LED="/sys/class/leds/red:fault"
GREEN_LED="/sys/class/leds/green:power"

while true; do
    if ping -c 1 -W 5 "$TARGET" > /dev/null 2>&1; then
        [ -d "$GREEN_LED" ] && echo 255 > "$GREEN_LED/brightness"
        [ -d "$RED_LED" ] && echo 0 > "$RED_LED/brightness"
    else
        [ -d "$GREEN_LED" ] && echo 0 > "$GREEN_LED/brightness"
        [ -d "$RED_LED" ] && echo 255 > "$RED_LED/brightness"
    fi
    sleep 1
done
EOF

chmod 500 /usr/bin/internet_led_watchdog.sh

cat > /etc/rc.local <<'EOF'
/usr/bin/internet_led_watchdog.sh &
echo "schedutil" | tee /sys/devices/system/cpu/cpufreq/policy*/scaling_governor
exit 0
EOF

cat > /etc/crontabs/root <<'EOF'
0 */6 * * * /etc/init.d/adblock-fast dl
0 3 * * * /sbin/reboot
EOF

/etc/init.d/adblock-fast restart

/**
 * A simple crashdump "daemon" that listens to the main mgurdy keys input
 * and triggers a mgsysinfo dump to /data/crashdump.html before issuing a 
 * reboot. Listens to simultaneous key-presses of D1, D2, D3, G1, G2
 */
#include <stdio.h>
#include <fcntl.h>
#include <linux/input.h>
#include <unistd.h>
#include <signal.h>
#include <stdlib.h>

#define NUMKEYS (5)

void int_handler(){
    exit(0);
}

void dump_and_restart()
{
    int err;

    system("/bin/echo 'heartbeat' > /sys/class/leds/string1/trigger");
    system("/bin/echo 'heartbeat' > /sys/class/leds/string2/trigger");
    system("/bin/echo 'heartbeat' > /sys/class/leds/string3/trigger");
    err = system("/usr/bin/wget -q -T 10 http://localhost:9999/live -O /data/crashdump.html");
    if (err) {
        // if getting the sysinfo fails, at least try to secure the current syslog
        system("cp /var/log/messages /data/crashdump.html");
    }
    system("/bin/sync");
    printf("rebooting in 2 seconds!\n");
    sleep(2);
    system("/sbin/reboot");
}

int main()
{
    char devname[] = "/dev/input/event2";
    int device = open(devname, O_RDONLY);
    unsigned int keystate = 0;
    int keys[NUMKEYS] = {106, 109, 112, 124, 127};
    int i;
    struct input_event ev;

    signal(SIGINT, int_handler);

    while(1)
    {
        read(device, &ev, sizeof(ev));
        if (ev.type != 1) continue;

        for (i=0; i < NUMKEYS; i++) {
            if (ev.code == keys[i])
                break;
        }

        if (i < NUMKEYS) {
            if (ev.value) {
                keystate |= (1UL << i);
            } else {
                keystate &= ~(1UL << i);
            }

            if (keystate == 31) {
                dump_and_restart();
                break;
            }
        }
    }
}

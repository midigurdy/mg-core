#include <fcntl.h>
#include <linux/input.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <unistd.h>
#include <errno.h>

#include "mg.h"
#include "sensors.h"
#include "utils.h"


static int mg_sensors_read_keys(struct mg_core *mg);
static int mg_sensors_read_wheel(struct mg_core *mg);

/* Setup the pollfd entries for keyboard and wheel input devices. Caller is
 * responsible for calling mg_sensors_cleanup() in case this function returns
 * an error.
 */
int mg_sensors_init(struct mg_core *mg)
{
    int ret = 0;
    int i;

    mg->sensor_fd_count = 0;

    ret = open(MG_KEYS_DEVICE, O_RDONLY | O_NONBLOCK);
    if (ret < 0) {
        perror("Unable to open keys input device");
        return ret;
    }
    mg->sensor_fds[0].fd = ret;
    mg->sensor_fds[0].events = POLLIN;
    mg->sensor_fd_count++;

    ret = open(MG_WHEEL_DEVICE, O_RDONLY | O_NONBLOCK);
    if (ret < 0) {
        perror("Unable to open wheel input device");
        return ret;
    }
    mg->sensor_fds[1].fd = ret;
    mg->sensor_fds[1].events = POLLIN;
    mg->sensor_fd_count++;

    /* initialize the keys to default values */
    memset(mg->keys, 0, sizeof(struct mg_key) * KEY_COUNT);

    /* Set initial key calibration values */
    for (i = 0; i < KEY_COUNT; i++) {
        mg->key_calib[i].pressure_adjust = 1.0f;
        mg->key_calib[i].velocity_adjust = 1.0f;
    }

    /* initialize wheel to default values */
    mg->wheel.position = 0;
    mg->wheel.distance = 0;
    mg->wheel.last_distance = 0;
    mg->wheel.elapsed_us = 0;
    mg->wheel.gain = 0;
    mg->wheel.speed = 0;

    return 0;
}


/* Attempts to close the poll input handles created by mg_sensors_init. This
 * function needs to succeed even if mg_sensors_init wasn't called beforehand.
 */
void mg_sensors_cleanup(struct mg_core *mg)
{
    int i;

    for (i=0; i < mg->sensor_fd_count; i++) {
        close(mg->sensor_fds[i].fd);
        mg->sensor_fd_count--;
    }
}


/* Check all sensor input devices for new data. Returns the number of input
 * events read or a negative error number. */
int mg_sensors_read(struct mg_core *mg)
{
    int ret;
    int count = 0;

    ret = poll(mg->sensor_fds, mg->sensor_fd_count, 0);
    if (ret < 0) {
        perror("Error polling sensor input devices");
        return ret;
    }

    if (mg->sensor_fds[0].revents & POLLIN) {
        ret = mg_sensors_read_keys(mg);
        if (ret < 0) {
            fprintf(stderr, "Error reading key events!\n");
            return ret;
        }
        count += ret;
    }

    if (mg->sensor_fds[1].revents & POLLIN) {
        ret = mg_sensors_read_wheel(mg);
        if (ret < 0) {
            fprintf(stderr, "Error reading wheel events!\n");
            return ret;
        }
        count += ret;
    }

    return count;
}


/* Read the keyboard sensor input device and return the number of key pressure
 * changes received or a negative value on error.
 */
static int mg_sensors_read_keys(struct mg_core *mg)
{
    int count = 0;
    int rd, num, i;
    struct input_event ev[10];
    struct mg_key *key;
    int val;
    int idx;

    for(;;) {
        rd = read(mg->sensor_fds[0].fd, ev, sizeof(ev));
        if (rd < 0) {
            if (errno == EAGAIN) {
                /* no more events to read */
                break;
            }
            else {
                perror("Read error on keys input device");
                return rd;
            }
        }

        num = rd / sizeof(struct input_event);
        for (i=0; i < num; i++) {
            if (ev[i].type != 3 || ev[i].code >= KEY_COUNT)
                continue;

            idx = ev[i].code;

            key = &mg->keys[idx];

            val = ev[i].value * mg->key_calib[idx].pressure_adjust;

            key->raw_pressure = ev[i].value;
            key->pressure = val;
            key->max_pressure = MAX(val, key->max_pressure);
            key->smoothed_pressure = mg_smooth(val, key->smoothed_pressure, 0.9);

            count++;
        }
    }

    return count;
}


#define DIST_UNSET (-99999)


/* Read the wheel sensor input device and return the number of position and/or
 * gain value updated received or a negative value on error.
 */
static int mg_sensors_read_wheel(struct mg_core *mg)
{
    int count = 0;
    int rd, num, i;
    struct input_event ev[10];

    /* if we get more than one position reading, we accumulate the times so we
     * can calculate the speed accordingly.
     */
    int total_us = 0;
    int distance = 0;

    /* need to save the values for next call as we only want to process
     * those values if we get a sync event (which could be delayed until the
     * next call to this function)
     *
     * TODO: check if this is really possible or if we always get a complete
     * event set including sync.
     */
    static int _dist = DIST_UNSET;
    static int _us = 0;

    for(;;) {
        rd = read(mg->sensor_fds[1].fd, ev, sizeof(ev));
        if (rd < 0) {
            if (errno == EAGAIN) {
                /* no more events to read */
                break;
            }
            else {
                perror("Read error on wheel input device");
                return rd;
            }
        }

        num = rd / sizeof(struct input_event);

        /* The wheel driver returns three event types:
         *   - position (0 - 16383)
         *   - distance travelled since last update
         *   - elapsed time since last position in microseconds
         *   - virtual gain of sensor chip (diagnostic data)
         *
         * Position and time are always sent together and only if
         * position actually changed.
         *
         * Gain can be sent separately, but also only if it has changed
         */
        for (i=0; i < num; i++) {
            /* position */
            if (ev[i].type == 3 && ev[i].code == 0) {
                mg->wheel.position = (16383 - ev[i].value);
            }
            /* distance */
            else if (ev[i].type == 3 && ev[i].code == 1) {
                _dist = ev[i].value;
            }
            /* time since last reading */
            else if (ev[i].type == 4 && ev[i].code == 1) {
                _us = ev[i].value;
            }
            /* sync event */
            else if (ev[i].type == 0 && ev[i].code == 0 &&
                    ev[i].value == 0) {
                if (_dist != DIST_UNSET) {
                    mg->wheel.last_distance = _dist;
                    distance += _dist;
                    total_us += _us;
                    _us = 0;
                    _dist = DIST_UNSET;
                }
                count++;
            }
            /* gain */
            else if (ev[i].type == 3 && ev[i].code == 2) {
                mg->wheel.gain = ev[i].value;
                count++;
            }
        }
    }

    if (total_us > 0) {
        mg->wheel.distance = distance;
        mg->wheel.elapsed_us = total_us;
   }

    return count;
}

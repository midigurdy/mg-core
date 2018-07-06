#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <libwebsockets.h>

#include "mg.h"
#include "server.h"

static struct lws_context *_context;
static volatile int _do_write = 0;

#define WHEEL_PACKET_SIZE (8)
#define WHEEL_MAX_PACKETS (100)
#define WHEEL_DATA_SIZE (WHEEL_PACKET_SIZE * WHEEL_MAX_PACKETS)

static unsigned char _wheel_buf[LWS_PRE + WHEEL_DATA_SIZE];
static int _wheel_buf_count = 0;
static unsigned char _wheel_data[WHEEL_DATA_SIZE];
static int _wheel_data_count = 0;
static int _wheel_client_count = 0;


#define KEYS_PACKET_SIZE (10)

struct key_data {
    int raw_pressure;
    int smoothed_pressure;
    int velocity;
    int action;
};

static unsigned char _keys_buf[LWS_PRE + KEYS_PACKET_SIZE * KEY_COUNT];
static int _keys_buf_count = 0;
static int _keys_client_count = 0;


static int _http_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len);

static int _wheel_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len);

static int _keys_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len);


static struct lws_protocols _protocols[] = {
    /* first protocol must always be HTTP handler */
    {"http-only", _http_callback, 0},
    {"wheel", _wheel_callback, 0},
    {"keys", _keys_callback, 0},
    {NULL, NULL, 0}
};


void *mg_server_thread(void *args)
{
    struct mg_core *mg = args;

    struct lws_context_creation_info context_info = {
        .port = 9000,
        .iface = NULL,
        .protocols = _protocols,
        .extensions = NULL,
        .ssl_cert_filepath = NULL,
        .ssl_private_key_filepath = NULL,
        .ssl_ca_filepath = NULL,
        .gid = -1,
        .uid = -1,
        .options = 0,
        .user = NULL,
        .ka_time = 0,
        .ka_probes = 0,
        .ka_interval = 0
    };

    prctl(PR_SET_NAME, "mgcore-server\0", NULL, NULL, NULL);

    lws_set_log_level(LLL_ERR | LLL_WARN, NULL);

    _context = lws_create_context(&context_info);

    if (_context == NULL) {
        fprintf(stderr, "lws init failed\n");
        return NULL;
    }

    // printf("starting websocket server...\n");

    while(!mg->should_stop) {
        lws_service(_context, 1000);
        if (_do_write) {
            if (_wheel_client_count) {
                lws_callback_on_writable_all_protocol(_context, &_protocols[1]);
            }
            if (_keys_client_count) {
                lws_callback_on_writable_all_protocol(_context, &_protocols[2]);
            }
            _do_write = 0;
        }
    }

    lws_context_destroy(_context);

    return NULL;
}


static int _http_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len)
{
    return 0;
}


void mg_server_record_wheel_data(int position, int speed, int chien_volume, int chien_speed)
{
    if (_wheel_client_count <= 0)
        return;

    if (_wheel_data_count >= WHEEL_DATA_SIZE - WHEEL_PACKET_SIZE)
        return;

    _wheel_data[_wheel_data_count++] = position & 0xFF;
    _wheel_data[_wheel_data_count++] = position >> 8;
    _wheel_data[_wheel_data_count++] = speed & 0xFF;
    _wheel_data[_wheel_data_count++] = speed >> 8;
    _wheel_data[_wheel_data_count++] = chien_volume & 0xFF;
    _wheel_data[_wheel_data_count++] = chien_volume >> 8;
    _wheel_data[_wheel_data_count++] = chien_speed & 0xFF;
    _wheel_data[_wheel_data_count++] = chien_speed >> 8;
}


void mg_server_report_wheel()
{
    if (_wheel_client_count <= 0 || _wheel_data_count == 0 || _wheel_buf_count)
        return;

    memcpy(&_wheel_buf[LWS_PRE], _wheel_data, _wheel_data_count);
    _wheel_buf_count = _wheel_data_count;

    memset(_wheel_data, 0, _wheel_data_count);
    _wheel_data_count = 0;

    _do_write = 1;
    lws_cancel_service(_context);
}


static int _wheel_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len)
{
    switch (reason) {
        case LWS_CALLBACK_ESTABLISHED:
            _wheel_client_count++;
            // printf("wheel websocket connection established: %d\n", _wheel_client_count);
            break;
        case LWS_CALLBACK_CLOSED:
            _wheel_client_count--;
            // printf("wheel websocket connection closed: %d\n", _wheel_client_count);
            break;
        case LWS_CALLBACK_SERVER_WRITEABLE:
            if (_wheel_buf_count) {
                lws_write(wsi, &_wheel_buf[LWS_PRE], _wheel_buf_count, LWS_WRITE_BINARY);
                _wheel_buf_count = 0;
            }
            break;
        default:
            break;
    }

    return 0;
}


int mg_server_key_client_count()
{
    return _keys_client_count;
}

void mg_server_report_keys(const struct mg_key *keys)
{
    int i;
    unsigned char *buf = &_keys_buf[LWS_PRE];
    static struct key_data prev_keys[KEY_COUNT] = {0};
    struct key_data *prev;
    const struct mg_key *key;
    static int calls = 0;

    if (calls++ < 50) {
        return;
    }
    calls = 0;

    if (_keys_client_count <= 0 || _keys_buf_count) {
        return;
    }

    for (i = 0; i < KEY_COUNT; i++) {
        key = &keys[i];
        prev = &prev_keys[i];

        if (key->raw_pressure != prev->raw_pressure ||
            key->smoothed_pressure != prev->smoothed_pressure ||
            key->velocity != prev->velocity ||
            key->action != prev->action) {

            prev->raw_pressure = key->raw_pressure;
            prev->smoothed_pressure = key->smoothed_pressure;
            prev->velocity = key->velocity;
            prev->action = key->action;

            *(buf++) = i & 0xFF;
            *(buf++) = i >> 8;
            *(buf++) = key->raw_pressure & 0xFF;
            *(buf++) = key->raw_pressure >> 8;
            *(buf++) = key->smoothed_pressure & 0xFF;
            *(buf++) = key->smoothed_pressure >> 8;
            *(buf++) = key->velocity & 0xFF;
            *(buf++) = key->velocity >> 8;
            *(buf++) = key->action & 0xFF;
            *(buf++) = key->action >> 8;

            _keys_buf_count += KEYS_PACKET_SIZE;
        }
    }

    if (_keys_buf_count) {
        _do_write = 1;
        lws_cancel_service(_context);
    }
}

static int _keys_callback(struct lws *wsi, enum lws_callback_reasons reason,
        void *user, void *in, size_t len)
{
    switch (reason) {
        case LWS_CALLBACK_ESTABLISHED:
            _keys_client_count++;
            // printf("keys websocket connection established: %d\n", _keys_client_count);
            break;
        case LWS_CALLBACK_CLOSED:
            _keys_client_count--;
            // printf("keys websocket connection closed: %d\n", _keys_client_count);
            break;
        case LWS_CALLBACK_SERVER_WRITEABLE:
            if (_keys_buf_count) {
                lws_write(wsi, &_keys_buf[LWS_PRE], _keys_buf_count, LWS_WRITE_BINARY);
                _keys_buf_count = 0;
            }
            break;
        default:
            break;
    }

    return 0;
}

#include <stdarg.h>
#include <stdint.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include <stdlib.h>

#include "synth.h"
#include "state.h"
#include "mg.h"


static int mg_setup(void **state)
{
    struct mg_core *mg = malloc(sizeof(struct mg_core));
    mg_state_init(&mg->state);
    *state = mg;
    return 0;
}

static int mg_teardown(void **state)
{
    free(*state);
    return 0;
}

static void test_synth_update_all_muted(void **state)
{
    int i;
    struct mg_core *mg = *state;

    mg_synth_update(mg);

    for (i = 0; i < 3; i++) {
        assert_int_equal(mg->state.melody[i].model.note_count, 0);
        assert_int_equal(mg->state.drone[i].model.note_count, 0);
        assert_int_equal(mg->state.trompette[i].model.note_count, 0);
    }
}

static void test_synth_update_all_unmuted_with_wheel_and_keys(void **state)
{
    int i;
    struct mg_core *mg = *state;

    for (i = 0; i < 3; i++) {
        mg->state.melody[i].muted = 0;
        mg->state.drone[i].muted = 0;
        mg->state.trompette[i].muted = 0;
    }

    mg->keys[1].pressure = 100;
    mg->keys[1].smoothed_pressure = 100;
    mg->keys[10].pressure = 200;
    mg->keys[10].smoothed_pressure = 200;
    mg->wheel.speed = 9;

    mg_synth_update(mg);

    for (i = 0; i < 3; i++) {
        assert_int_equal(mg->state.melody[i].model.note_count, 1);
        assert_int_equal(mg->state.drone[i].model.note_count, 0);
        assert_int_equal(mg->state.trompette[i].model.note_count, 0);
    }
}

static void test_synth_unmuted_melody_plays_base_key(void **state)
{
    int i;
    struct mg_core *mg = *state;

    mg->state.melody[0].muted = 0;

    mg_synth_update(mg);

    assert_int_equal(mg->state.melody[0].model.note_count, 1);
    assert_int_equal(mg->state.melody[1].model.note_count, 0);
    assert_int_equal(mg->state.melody[2].model.note_count, 0);
}


int run_synth_tests(void)
{
	const struct CMUnitTest tests[] = {
        cmocka_unit_test_setup_teardown(test_synth_update_all_muted, mg_setup, mg_teardown),
        cmocka_unit_test_setup_teardown(test_synth_unmuted_melody_plays_base_key, mg_setup, mg_teardown),
        cmocka_unit_test_setup_teardown(test_synth_update_all_unmuted_with_wheel_and_keys, mg_setup, mg_teardown),
    };

    return cmocka_run_group_tests_name("synth", tests, NULL, NULL);
}

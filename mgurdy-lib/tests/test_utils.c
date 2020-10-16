#include <stdarg.h>
#include <stdint.h>
#include <stddef.h>
#include <setjmp.h>
#include <cmocka.h>

#include "utils.h"


/* utils_map tests */

static void test_map_lower_bound(void **state)
{
    assert_int_equal(map(0, 0, 1, 0, 1), 0);
}

static void test_map_upper_bound(void **state)
{
    assert_int_equal(map(1, 0, 1, 0, 1), 1);
}

static void test_map_equal_ranges(void **state)
{
    int i;

    for (i=0; i<100; i++)
        assert_int_equal(map(i, 0, 100, 0, 100), i);
}

static void test_map_smaller_input_range(void **state)
{
    int i;

    for (i=0; i<10; i++)
        assert_int_equal(map(i, 0, 10, 0, 100), i * 10);
}

static void test_map_larger_input_range(void **state)
{
    assert_int_equal(map(0, 0, 9, 1, 5), 1);
    assert_int_equal(map(1, 0, 9, 1, 5), 1);
    assert_int_equal(map(2, 0, 9, 1, 5), 2);
    assert_int_equal(map(3, 0, 9, 1, 5), 2);
    assert_int_equal(map(4, 0, 9, 1, 5), 3);
    assert_int_equal(map(5, 0, 9, 1, 5), 3);
    assert_int_equal(map(6, 0, 9, 1, 5), 4);
    assert_int_equal(map(7, 0, 9, 1, 5), 4);
    assert_int_equal(map(8, 0, 9, 1, 5), 5);
    assert_int_equal(map(9, 0, 9, 1, 5), 5);
}

static void test_map_outside_input_min_max(void **state)
{
    assert_int_equal(map(-999, 0, 100, 0, 100), 0);
    assert_int_equal(map(999, 0, 100, 0, 100), 100);
}

static void test_map_negative_input_range(void **state)
{
    assert_int_equal(map(-20, -20, -10, 0, 2), 0);
    assert_int_equal(map(-15, -20, -10, 0, 2), 1);
    assert_int_equal(map(-10, -20, -10, 0, 2), 2);
}

static void test_map_bipolar_input_range(void **state)
{
    assert_int_equal(map(-10, -10, 10, -5, 5), -5);
    assert_int_equal(map(0, -10, 10, -5, 5), 0);
    assert_int_equal(map(10, -10, 10, -5, 5), 5);
}

static void test_map_negative_output_range(void **state)
{
    assert_int_equal(map(0, 0, 20, -3, -1), -3);
    assert_int_equal(map(10, 0, 20, -3, -1), -2);
    assert_int_equal(map(20, 0, 20, -3, -1), -1);
}

static void test_map_bipolar_output_range(void **state)
{
    assert_int_equal(map(0, 0, 20, -1, 1), -1);
    assert_int_equal(map(10, 0, 20, -1, 1), 0);
    assert_int_equal(map(20, 0, 20, -1, 1), 1);
}


/* utils map_value tests */
static void test_map_value_single_range(void **state)
{
    struct mg_map mapping = {
        .ranges = {
            {0, 0},
        },
        .count = 1,
    };

    assert_int_equal(map_value(0, &mapping), 0);
}

static void test_map_value_outside_min_max(void **state)
{
    struct mg_map mapping = {
        .ranges = { 
            {0, 0},
            {10, 10},
        },
        .count = 2,
    };

    assert_int_equal(map_value(-999, &mapping), 0);
    assert_int_equal(map_value(999, &mapping), 10);
}

static void test_map_value_negative_start(void **state)
{
    struct mg_map mapping = {
        .ranges = {
            {-4, 0},
            { 0, 2},
            { 4, 4},
        },
        .count = 3,
    };

    assert_int_equal(map_value(-3, &mapping), 0);
    assert_int_equal(map_value(-2, &mapping), 1);
    assert_int_equal(map_value(0, &mapping), 2);
    assert_int_equal(map_value(2, &mapping), 3);
    assert_int_equal(map_value(4, &mapping), 4);
}

static void test_map_value_smaller_input_ranges(void **state)
{
    struct mg_map mapping = {
        .ranges = {
            {0, 10},
            {2, 20},
            {4, 30},
            {6, 40},
        },
        .count = 4,
    };

    assert_int_equal(map_value(0, &mapping), 10);
    assert_int_equal(map_value(1, &mapping), 15);
    assert_int_equal(map_value(2, &mapping), 20);
    assert_int_equal(map_value(5, &mapping), 35);
    assert_int_equal(map_value(6, &mapping), 40);
}


static void test_smooth_reaches_upper_bound(void **state)
{
    static int val = 0;
    static int prev = 0;
    static int equal_count = 0;
    static int bound_count = 0;

    for(;;) {
        val = mg_smooth(8000, val, 0.9);
        if (val == 8000) {
            bound_count++;
            if (bound_count > 10)
                break;
        }
        if (prev == val) {
            equal_count++;
            if (equal_count > 10) {
                assert_int_equal(0, val);
                break;
            }
        }
        prev = val;
    }

    assert_true(1);
}

static void test_smooth_reaches_lower_bound(void **state)
{
    static int val = 8000;
    static int prev = 0;
    static int equal_count = 0;
    static int bound_count = 0;

    for(;;) {
        val = mg_smooth(0, val, 0.9);
        if (val == 0) {
            bound_count++;
            if (bound_count > 10)
                break;
        }
        if (prev == val) {
            equal_count++;
            if (equal_count > 10) {
                assert_int_equal(0, val);
                break;
            }
        }
        prev = val;
    }

    assert_true(1);
}


int run_utils_tests(void)
{
	const struct CMUnitTest tests[] = {
        cmocka_unit_test(test_map_lower_bound),
        cmocka_unit_test(test_map_upper_bound),
        cmocka_unit_test(test_map_equal_ranges),
        cmocka_unit_test(test_map_outside_input_min_max),
        cmocka_unit_test(test_map_smaller_input_range),
        cmocka_unit_test(test_map_larger_input_range),
        cmocka_unit_test(test_map_negative_input_range),
        cmocka_unit_test(test_map_bipolar_input_range),
        cmocka_unit_test(test_map_negative_output_range),
        cmocka_unit_test(test_map_bipolar_output_range),

        cmocka_unit_test(test_map_value_single_range),
        cmocka_unit_test(test_map_value_negative_start),
        cmocka_unit_test(test_map_value_outside_min_max),
        cmocka_unit_test(test_map_value_smaller_input_ranges),

        cmocka_unit_test(test_smooth_reaches_upper_bound),
        cmocka_unit_test(test_smooth_reaches_lower_bound),
    };

    return cmocka_run_group_tests_name("utils", tests, NULL, NULL);
}

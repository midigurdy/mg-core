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


/* utils multimap tests */
static void test_multimap_single_range(void **state)
{
    int ranges[][2] = {
        {0, 0},
    };

    assert_int_equal(multimap(0, ranges, 1), 0);
}

static void test_multimap_outside_min_max(void **state)
{
    int ranges[][2] = {
        {0, 0},
        {10, 10},
    };

    assert_int_equal(multimap(-999, ranges, 2), 0);
    assert_int_equal(multimap(999, ranges, 2), 10);
}

static void test_multimap_negative_start(void **state)
{
    int ranges[][2] = {
        {-4, 0},
        { 0, 2},
        { 4, 4},
    };

    assert_int_equal(multimap(-3, ranges, 3), 0);
    assert_int_equal(multimap(-2, ranges, 3), 1);
    assert_int_equal(multimap(0, ranges, 3), 2);
    assert_int_equal(multimap(2, ranges, 3), 3);
    assert_int_equal(multimap(4, ranges, 3), 4);
}

static void test_multimap_smaller_input_ranges(void **state)
{
    int ranges[][2] = {
        {0, 10},
        {2, 20},
        {4, 30},
        {6, 40},
    };

    assert_int_equal(multimap(0, ranges, 4), 10);
    assert_int_equal(multimap(1, ranges, 4), 15);
    assert_int_equal(multimap(2, ranges, 4), 20);
    assert_int_equal(multimap(5, ranges, 4), 35);
    assert_int_equal(multimap(6, ranges, 4), 40);
}


static void test_smooth_reaches_upper_bound(void **state)
{
    static int val = 0;
    static int prev = 0;
    static int equal_count = 0;
    static int bound_count = 0;

    for(;;) {
        val = mg_smooth(8000, val, 0.9);
        printf("val: %d\n", val);
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
        printf("val: %d\n", val);
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

        cmocka_unit_test(test_multimap_single_range),
        cmocka_unit_test(test_multimap_negative_start),
        cmocka_unit_test(test_multimap_outside_min_max),
        cmocka_unit_test(test_multimap_smaller_input_ranges),

        cmocka_unit_test(test_smooth_reaches_upper_bound),
        cmocka_unit_test(test_smooth_reaches_lower_bound),
    };

    return cmocka_run_group_tests_name("utils", tests, NULL, NULL);
}

int run_utils_tests(void);
int run_synth_tests(void);

int main(void)
{
    int err;

    err = run_utils_tests();
    err += run_synth_tests();

    return err;
}

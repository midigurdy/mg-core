import os

from mg.conf import settings

TEST_DIR = os.path.dirname(__file__)

settings.data_dir = os.path.join(TEST_DIR, 'data')
settings.load(os.path.join(TEST_DIR, 'test.cfg'))

def read_firmware_version():
    with open('/etc/mg-version', 'r') as f:
        return f.read().strip()


try:
    VERSION = read_firmware_version()
except:
    VERSION = 'devel'

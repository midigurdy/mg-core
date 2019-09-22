import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 9999

CRASHDUMP_FILE = '/data/crashdump.html'

INDEX_TEMPLATE = '''
<html>
    <body>
        <h1>MidiGurdy System Info</h1>
        <p>
            <a href="/live">View current system info</a><br/>
            <a href="/live/download">Download current system info</a>
        </p>
        {crashdump}
    </body>
    </html>
'''

CRASHDUMP_LINKS_TEMPLATE = '''
<h2>Crash Handler Info</h2>
<a href="/crashdump/show">View system info by crash handler</a><br/>
<a href="/crashdump/download">Download system info by crash handler</a><br/><br/>
<form action="/crashdump/remove" method="post">
    <button type="submit">Remove the current crash handler info</button>
</form>
'''

CMD_TEMPLATE = '''
<h2>{cmd}</h2>
<pre>{output}</pre>
'''

SYSINFO_TEMPLATE = '''
<html>
    <head>
        <style>
            pre {{
                padding: 1em;
                background: lightgrey;
                border: 1px solid #ddd;
            }}
            h2 {{
                margin-top: 2em;
            }}
        </style>
    </head>
    <body>
        <h1>MidiGurdy System Info</h1>

        {results}
    </body>
</html>
'''


class Handler(BaseHTTPRequestHandler):

    def respond(self, content, content_type='text/html', status_code=200, filename=None):
        self.send_response(status_code)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-type', content_type)
        if filename is not None:
            self.send_header("Content-Disposition", 'attachment; filename="{}"'.format(filename))
        self.end_headers()
        self.wfile.write(bytes(content, 'UTF-8'))

    def do_GET(self):
        if self.path == '/':
            self.return_index()
        elif self.path == '/live':
            self.return_live_sysinfo()
        elif self.path == '/live/download':
            self.return_live_sysinfo(download=True)
        elif self.path == '/crashdump/show':
            self.return_crashdump()
        elif self.path == '/crashdump/download':
            self.return_crashdump(download=True)
        else:
            self.respond('Not found!', status_code=404)

    def do_POST(self):
        if self.path == '/crashdump/remove':
            self.remove_crashdump()
        else:
            self.respond('Not found!', status_code=404)

    def return_index(self):
        if self.crashdump_available():
            crashdump = CRASHDUMP_LINKS_TEMPLATE
        else:
            crashdump = ''
        self.respond(INDEX_TEMPLATE.format(crashdump=crashdump))

    def return_crashdump(self, download=False):
        try:
            with open(CRASHDUMP_FILE) as f:
                self.respond(f.read(), filename='crashdump.html' if download else None)
        except Exception:
            self.respond('File not found!', status_code=404)
            return

    def remove_crashdump(self):
        try:
            os.remove(CRASHDUMP_FILE)
        except Exception as e:
            self.respond(str(e), status_code=500)
            return

        self.send_response(301)
        self.send_header('Location','/')
        self.end_headers()

    def return_live_sysinfo(self, download=False):
        cmds = (
            '/usr/bin/free -m',
            '/bin/ps -T',
            '/usr/bin/top -b -n 1',
            '/usr/bin/head -n 2000 /var/log/messages',
            '/usr/bin/tail -n 2000 /var/log/messages',
            '/bin/cat /proc/interrupts',
            '/bin/cat /sys/class/power_supply/axp20x-battery/uevent',
            '/bin/cat /sys/class/power_supply/axp20x-ac/uevent',
            '/bin/cat /sys/class/power_supply/axp20x-usb/uevent',
        )
        results = [CMD_TEMPLATE.format(cmd=cmd, output=call(cmd)) for cmd in cmds]
        self.respond(
            SYSINFO_TEMPLATE.format(results='\n'.join(results)),
            filename='sysinfo.html' if download else None)

    def crashdump_available(self):
        return os.path.isfile(CRASHDUMP_FILE)



def call(cmd):
    try:
        return subprocess.run(cmd.split(), stdout=subprocess.PIPE, check=True).stdout.decode()
    except Exception as e:
        return 'Error executing {}: {}'.format(cmd, e)



if __name__ == '__main__':
    with HTTPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

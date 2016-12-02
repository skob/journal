#!/bin/python2
import signal
from tornado import web, gen, escape
from tornado.options import define, options
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.iostream import StreamClosedError
import json, uuid, os, re
from systemd import journal

def journalctl():
    j = journal.Reader(path=options.directory)
    j.seek_tail()
    j.get_previous()
    while True:
        event = j.wait(-1)
        if not event:
            continue
        for entry in j:
            if entry['MESSAGE'] != "":
                try:
                    su = entry['_SYSTEMD_UNIT']
                except KeyError:
                    su = "systemd"
                if _filter(su):
                    result = { "hostname": entry['_HOSTNAME'], "unit": su, "datetime": str(entry['__REALTIME_TIMESTAMP'] ), "message": entry['MESSAGE'].decode('utf-8') , "priority": entry['PRIORITY']}
                    yield(result)

def journaluniq(param):
    j = journal.Reader(path=options.directory)
    t = j.query_unique(param)
    if param == '_SYSTEMD_UNIT':
        t = [x for x in t if _filter(x)]
    j.close()
    return t

def _filter(query):
    for pattern in options.UNITS_RE:
        pattern = re.compile(pattern)
        if bool(re.search(pattern, query)):
            return True
    return False

class DataSource(object):
    def __init__(self, initial_data=None):
        self._data = initial_data
    
    @property
    def data(self):
        return self._data
        
    @data.setter
    def data(self, new_data):
        self._data = new_data

class EventSource(web.RequestHandler):
    def initialize(self, source):
        self.source = source
        self._last = None

    @gen.coroutine
    def prepare(self):
        self.sunit = ""
        self.host = ""
        self.priority = 7
        user_id_cookie = self.get_secure_cookie("user_id")
        if not user_id_cookie:
            self.finish()
        for c in CL:
            if ( c.get_secure_cookie("user_id") == user_id_cookie and c != self ):
                self.sunit = c.sunit
                self.host = c.host
                self.priority = c.priority
        CL.append(self)
        
    @property
    def sunit(self):
        return self._sunit
    @sunit.setter
    def sunit(self, value):
        self._sunit = value
    @property
    def host(self):
        return self._host
    @host.setter
    def host(self, value):
        self._host = value
    @property
    def priority(self):
        return self._priority
    @priority.setter
    def priority(self, value):
        self._priority = value

    @gen.coroutine
    def publish(self, data):
        try:
            result = json.dumps(data)
            self.write('retry: 10000\ndata: {}\n\n'.format(result.encode('utf-8')))
            yield self.flush()
        except StreamClosedError:
            pass

    @gen.coroutine
    def get(self):
        self.set_header('content-type', 'text/event-stream')
        self.set_header('cache-control', 'no-cache')
        while True:
            if self.source.data != self._last and \
               self.source.data and \
               (self.source.data['unit'] == self.sunit or self.sunit == "") and \
               (self.source.data['hostname'] == self.host or self.host == "") and \
               (self.source.data['priority'] <= self.priority ):
                    yield self.publish(self.source.data)
                    self._last = self.source.data
            else:
                yield gen.sleep(0.005)
        self.clear_cookie("user_id")
        if self in CL:
            CL.remove(self)

    def post(self):
        args = escape.json_decode(self.request.body)
        for m in ALLOWED_MODIFIERS.keys():
            if m == "priority":
                setattr(self, m, int(args[0][m]))
            else:
                setattr(self, m, args[0][m])
        for c in CL:
            if ( c.get_secure_cookie("user_id") == self.get_secure_cookie("user_id")):
                c.sunit = self.sunit
                c.host = self.host
                c.priority = self.priority
        self.finish()

class MainHandler(web.RequestHandler):
    @gen.coroutine
    def prepare(self):
        user_id_cookie = self.get_secure_cookie("user_id")
        if not user_id_cookie:
            self.set_secure_cookie("user_id", str(uuid.uuid4()))

    @gen.coroutine
    def get(self):
        self.render("./web/index.html")

class AjaxHandler(web.RequestHandler):
    def prepare(self):
        user_id_cookie = self.get_secure_cookie("user_id")
        if not user_id_cookie:
            self.finish()

    def get(self, slug):
        if slug in ALLOWED_MODIFIERS.keys():
            uniq = list(journaluniq(ALLOWED_MODIFIERS[slug]))
            self.set_header('content-type', 'application/json')
            self.set_header('cache-control', 'no-cache')
            k = {"items": []}
            for key, unit in enumerate(uniq):
                k["items"].append({"id": unit, "name": unit})
            self.write(json.dumps(k))
        self.finish

def main():
    settings = {
        'cookie_secret' : "OrTiV4Nj8eTy0GsQJE2KMrNVdVU"
    }
    handlers = [
            (r'/', MainHandler),
            (r'/static/(.*)', web.StaticFileHandler, {"path": "./web/static/"}),
            (r'/get/([^/]+)', AjaxHandler),
            (r'/events', EventSource, dict(source=publisher)) ]

    app = web.Application(handlers, **settings)
    server = HTTPServer(app)
    server.listen(options.port, address=options.ipaddr)
    signal.signal(signal.SIGINT, lambda x, y: IOLoop.instance().stop())
    IOLoop.instance().start()

if __name__ == "__main__":
    CL = []
    ALLOWED_MODIFIERS = { 'sunit': '_SYSTEMD_UNIT', 'host': '_HOSTNAME', 'priority': 'PRIORITY' }
    define ("directory" , default = None, help="Directory of journals, usualy /var/log/journal/remote or empty for local journals", group="General")
    define ("ipaddr" , default = '127.0.0.1', help="ip address to bind to", group="General")
    define ("port" , default = 8888, help="port to bind to", group="General")
    define ("UNITS_RE" , default = [ "^uml_" , "^ssh" ], help="list of regexps for filtering systemd units names", multiple=True, group="Filtering")
    options.parse_command_line()
    generator = journalctl()
    publisher = DataSource(next(generator))
    def get_next():
        publisher.data = next(generator)
    checker = PeriodicCallback(lambda: get_next(), 10.)
    checker.start()
    main()

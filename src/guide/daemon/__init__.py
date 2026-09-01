"""The daemon: one local process, an inbox, and the page that draws it.

``app``        the ASGI application, its routes and its security headers
``api``        the versioned HTTP surface the page and the CLI both speak
``service``    store + event bus + one lock per batch, with no HTTP in sight
``events``     server-sent events, so a page hears about a batch that arrives
``lifecycle``  binding a port, finding a daemon, starting and stopping one
``skillpage``  the routes behind "install the skill"
"""

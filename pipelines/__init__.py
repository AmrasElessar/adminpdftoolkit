"""Background-thread workers and their data pipelines.

Lifted out of ``app.py`` during the S5 split so each one owns its module.
Routers stay thin: they validate input, persist the job, and start a thread
pointing at one of these workers.
"""

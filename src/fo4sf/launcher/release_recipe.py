"""One managed release transaction across a recipe's component commands."""
from pathlib import Path

from . import instance, release_install as ri, save_release as sr, settings


class Transaction:
    def __init__(self, config, steps):
        sr._keys(config, ("settings", "declaration"), "managed release recipe")
        if any(not isinstance(p, str) or not p or not Path(p).is_absolute() for p in config.values()):
            raise ValueError("managed release recipe needs absolute settings and declaration paths")
        self.config = dict(config)
        self.raw = {k: ri.read(p) for k, p in self.config.items()}
        if any(raw is None for raw in self.raw.values()):
            raise ValueError("managed release recipe input is missing")
        saved = ri.decode(self.raw["settings"])
        if not isinstance(saved, dict) or set(saved) - set(settings.KEYS):
            raise ValueError("managed recipe settings have unknown fields or shape")
        self.values = settings.defaults()
        self.values.update({k: settings.coerce(k, v) for k, v in saved.items()})
        sr.declaration(ri.decode(self.raw["declaration"]))
        folder = self.values["instance"]
        if not folder or not Path(folder).is_absolute():
            raise ValueError("managed recipe needs a confirmed absolute instance")
        my_games = self.values["my_games"]
        if not my_games or not Path(my_games).is_absolute() or not Path(my_games).is_dir():
            raise ValueError("managed recipe needs a confirmed My Games folder")
        for step in steps:
            instance.check_run(folder, step["argv"], cwd=step["cwd"])
        self.environment = instance.env_for(folder)
        self.expected = None

    def verify(self):
        if any(ri.read(p) != self.raw[k] for k, p in self.config.items()):
            raise ValueError("managed recipe inputs changed; preserve pending release and repeat original inputs")
        if self.expected is not None and ri.read(Path(self.values["instance"]) / instance.RECORD) != self.expected["receipt"]:
            raise ValueError("managed recipe instance receipt changed; preserve pending release")

    def begin(self):
        self.verify()
        self.expected = ri.begin(self.values, self.config["declaration"])

    def finish(self, say):
        self.verify()
        ri.finish(self.values, self.config["declaration"], self.expected, say=say)

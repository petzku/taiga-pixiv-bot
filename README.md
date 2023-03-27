# taiga-pixiv-bot

Discord bot to upload pixiv images as attachments.

Designed to just complement [Saucybot](https://github.com/Sn0wCrack/saucybot-discord), so it only reacts to messages with spoilers (as those diable Saucybot's replies). Will spoiler any images from spoilered links, and hides the pixiv embeds from the original message afterwards.

## Setup

1. (Optional, recommended) Create a virtualenv and activate it
2. Copy `config.py.sample` to `config.py` and configure appropriately
3. Install the packages from `requirements.txt`
4. Run `python pixiv_auth.py login` to generate the authentication data (see https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362 for instructions)

```sh
$ cp config.py.sample config.py
$ nano config.py  # in your choice of editor
$ python -m venv venv
$ . venv/bin/activate
(venv) $ pip install -r requirements.txt
(venv) $ python pixiv_auth.py login
```

After this, you can run the bot by executing the main program, `main.py`. Remember to enable the virtualenv if it's not active anytime after the setup.

```sh
$ . venv/bin/activate
(venv) $ python main.py
```

## Development

`requirements-dev.txt` lists more dependencies used for development—such as `mypy` and `black` for typechecking and linting/formatting, as well as type signatures for some libraries.

from regulated_eval.cli import app
for c in app.registered_commands:
    print(f"name={c.name!r} callback={c.callback.__name__ if c.callback else None}")

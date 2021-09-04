---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.2'
      jupytext_version: 1.5.2
  kernelspec:
    display_name: Python 3
    language: python
    name: python3
---

# Demonstration of Blocking UI

File [`ui.py`](../../edit/notebooks/ui.py) in [this
folder](../../tree/notebooks) implements a blocking User Interface that asks
user to select a color. If no action happens within 10 seconds, default value is
returned.

Run this notebook using `Cell -> Run All` menu option.

```python
from ipywidgets import HTML
from ui import blocking_ui

color, mode = await blocking_ui(default='beige', timeout=10)
```

```python
if mode == 'user':
    print(f"So you picked '{color}'")
else:
    print('Try to click faster next time')

HTML(f'''
<div style="width:100px;
            height:100px;
            background:{color};
            padding:10px;
            border-color:black;
            border-style:solid"><b>{color}</b></div>''')
```

```python
# this cell throws Exception
print(no_such_var)
```

```python
print("This cell should not execute")
```

```python
print("This won't run either")
```

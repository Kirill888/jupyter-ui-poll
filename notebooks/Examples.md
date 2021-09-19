---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.11.3
  kernelspec:
    display_name: Python 3
    language: python
    name: python3
---

# Introduction

This notebook introduces `jupyter_ui_poll` library.

This library allows one to implement a "blocking GUI" inside a Jupyter
environment. It does not implement new GUI primitives, rather it allows use of
existing `ipywidgets` based libraries in a blocking fashion. It also gives you
mechanisms to maintain interactivity of widgets while executing a long-running
cell.

After going through this notebook you should also checkout a more [complex
example](ComplexUIExample.ipynb), it demonstrates implementation a blocking UI
primitive as a library.

```python
import asyncio
import time

import ipywidgets as w
from IPython.display import display
from jupyter_ui_poll import run_ui_poll_loop, ui_events, with_ui_events
```

## Simplest UI widget

Create a button that displays number of times it was clicked. We will be using it for testing.

Go on, run the cell below and click the button few times.

```python
def on_click(btn):
    n = int(btn.description)
    btn.description = str(n + 1)


def test_button():
    """
    Create button that displays number of times it was clicked
    """
    btn = w.Button(description="0")
    btn.on_click(on_click)
    return btn


display(test_button())
```

## Waiting for user action

Example of using `ui_events` function. This is the foundational function in
`jupyter-ui-poll` library, all other methods use it under the hood. `ui_events`
returns a function your code should call to process UI events that happened so
far while executing a long-running cell. This requires temporarily modifying
internals of the running IPython kernel, hence this function needs to be used
inside `with` statement, so that IPython state can be restored to normal once
your code is done, even if errors have happened.

You can supply how many events should be processed every time you call `ui_poll`
function, default is `1`. You probably want to use larger value if you have
highly interactive widgets that generate a lot of events, like a map, or if your
poll frequency is low. One should aim for something like 100 events per second.
If you notice that UI lags and is not responsive try increasing poll frequency
and if that is not possible, increase number of UI events you process per
polling interval.

- Cell below presents a button with click count display
- Roughly ten times a second we print click count so far
- When click count reaches 10, we stop

```python
btn = test_button()
print("Press this button 10 times to terminate")
display(btn)

with ui_events() as ui_poll:
    while int(btn.description) < 10:
        print(btn.description, end="")
        ui_poll(11)  # Process upto 11 ui events per iteration
        time.sleep(0.1)

print("... done")
```

## Process Long Sequence while Responding to UI events

Sometimes you want to process a large number of small jobs in the notebook, but
still want to respond to UI events, like button clicks. Maybe you want to
terminate computation early and get the result so far, or change some parameter
mid-flight. Providing interactive feedback to the user about the state of the
computation is another example.

Just wrap an iterator in `with_ui_events` function, you will get the same data
out, but also UI events will be processed in between each item.

```python
btn = test_button()
print("Press this button a few times")
display(btn)

for i in with_ui_events(range(55), 10):  # Process upto 10 ui events per iteration
    if int(btn.description) >= 5:
        print("✋", end="")
        break  # Test early exit
    print(btn.description, end="")  # Verify UI state changes
    time.sleep(0.1)  # Simulate blocking computation
print("... done")
```

Try changing code in the cell above to run without `with_ui_events`

```diff
- for i in with_ui_events(range(55), 10):
+ for i in range(55):
```

You will see that the button text no longer updates as you click it, but instead
`on_click` events will be processed as soon as the cell finishes executing.


## Example using run_ui_poll_loop

A common scenario is to wait for some input from the user, validate it, and if
successful continue with the execution of the rest of the notebook.
`run_ui_poll_loop` is handy in this case. You give it a function to call at a
regular interval. This function should return `None` while user input is still
incomplete. Once all data is entered this function should extract it from the UI
and return as python construct of some sort (tuple, dictionary, single number,
anything but `None`) to be used by the rest of the notebook.

Cell below will:

- Display a button
- Ask user to press it 10 times
- Report how many seconds it took

Try using `Cell->Run All Below`, everything should still work as expected.

```python
t0 = time.time()
xx = ["-_-", "o_o"]


def on_poll():
    """This is called repeatedly by run_ui_poll_loop

    Return None if condition hasn't been met yet

    Return some result once done, in this example result
    is a number of seconds it took to press the button 10 times.
    """
    if int(btn.description) < 10:
        print(xx[0], end="\r", flush=True)
        xx[:] = xx[::-1]
        return None  # Continue polling

    # Terminate polling and return final result
    return time.time() - t0


btn = test_button()
print("Press button 10 times")
display(btn)

dt = run_ui_poll_loop(on_poll, 1 / 15)
print("._.")  # This should display the text in the output of this cell
n_times = "10 times"  # To verify that the rest of this cell executes before executing cells below
```

Cell below uses `dt` and `n_times` that are set in the cell above, so it's
important that it doesn't execute until `dt` is known.

```python
print(f"Took {dt:.1f} seconds to click {n_times}")
```

Cell  below contains intentional error.

Cells below this one should not execute as part of `Run All Below` command you can still run them later of course.

```python
this_will_raise_an_error()
```

## Async Operations

We also support async mode of operation if desired. Just use `async with` or `async for`.

```python
btn = test_button()
print("Press this button 10 times to terminate")
display(btn)

async with ui_events() as ui_poll:
    while int(btn.description) < 10:
        print(btn.description, end="")
        await ui_poll(11)  # Process upto 11 ui events per iteration
        await asyncio.sleep(0.1)  # Simulate async processing

print("... done")
```

### Async Iterable

Iterable returned from `with_ui_events` can also be used in async context. It can wrap async/sync iterators, the result can be iterated with either plain `for` or `async for` when wrapping normal iterators, and only with `async for` when wrapping `async` iterators. 

```python
btn = test_button()
print("Press this button a few times")
display(btn)

async for i in with_ui_events(range(55), 10):  # Process upto 10 ui events per iteration
    if int(btn.description) >= 5:
        print("✋", end="")
        break  # Test early exit
    print(btn.description, end="")  # Verify UI state changes
    await asyncio.sleep(0.1)  # Simulate Async computation
print("... done")
```

### Test Async Iterable wrapping

```python
from collections import abc


async def async_range(n):
    for i in range(n):
        yield i


its0 = async_range(55)
its = with_ui_events(its0, 10)

print(
    f"""Iterable:      {isinstance(its0, abc.Iterable)}, {isinstance(its, abc.Iterable)} 
AsyncIterable: {isinstance(its0, abc.AsyncIterable)}, {isinstance(its, abc.AsyncIterable)}"""
)
```

One can create and wrap iterator in an earlier cell and use it later.

```python
btn = test_button()
print("Press this button a few times")
display(btn)

async for i in its:  # Process upto 10 ui events per iteration
    if int(btn.description) >= 5:
        print("✋", end="")
        break  # Test early exit
    print(btn.description, end="")  # Verify UI state changes
    await asyncio.sleep(0.1)  # Simulate Async computation
print("... done")
```

------------------------------------------------------------

===============
jupyter-ui-poll
===============

.. image:: https://mybinder.org/badge_logo.svg
 :target: `run it`_

Block Jupyter cell execution while interacting with widgets.

This library is for people familiar with ``ipywidgets`` who want to solve the
following problem:

1. Display User Interface in Jupyter [#]_ using ``ipywidgets`` [#]_ or similar
2. Wait for data to be entered (this step is surprisingly non-trivial to implement)
3. Use entered data in cells below

You want to implement a notebook like the one below

.. code-block:: python

   # cell 1
   ui = make_ui()
   display(ui)
   data = ui.wait_for_data()

   # cell 2
   do_things_with(data)

   # cell 3.
   do_more_tings()

And you want to be able to execute ``Cells -> Run All`` menu option and still get correct output.

This library assists in implementing your custom ``ui.wait_for_data()`` poll loop.
If you have tried implementing such workflow in the past you'll know that it is
not that simple. If you haven't, see `Technical Details`_ section below for an
explanation on why it's hard and how ``jupyter-ui-poll`` solves it.

Quick, self contained example:

.. code-block:: python

   import time
   from ipywidgets import Button
   from jupyter_ui_poll import ui_events

   # Set up simple GUI, button with on_click callback
   # that sets ui_done=True and changes button text
   ui_done = False
   def on_click(btn):
       global ui_done
       ui_done = True
       btn.description = '👍'

   btn = Button(description='Click Me')
   btn.on_click(on_click)
   display(btn)

   # Wait for user to press the button
   with ui_events() as poll:
       while ui_done is False:
           poll(10)          # React to UI events (upto 10 at a time)
           print('.', end='')
           time.sleep(0.1)
   print('done')

For a more detailed tutorial see `Example notebook`_, you can also `run it`_ right now using awesome `Binder`_ service.

Installation
============

This library requires Python 3.6 or greater.

.. note::

   Starting from version ``0.2.0`` we only support ``ipykernel`` version 6
   series. Version 6 of ``ipykernel`` now uses async internally, and so this
   library also switched to async. If you need to support ``ipykernel`` 5
   series, then you need to use ``jupyter-ui-poll==0.1.3`` which had synchronous
   interface.


.. code-block::

  pip install jupyter-ui-poll


Technical Details
=================

Jupyter widgets (``ipywidgets``) provide an excellent foundation to develop
interactive data investigation apps directly inside Jupyter notebook or Jupyter
lab environment. Jupyter is great at displaying data and ``ipywidgets`` provide
a mechanism to get input from the user in a more convenient way than entering or
changing Python code inside a Jupyter cell. Developer can construct an
interactive user interface often used to parameterise information display or
other kinds of computation.

Interactivity is handled with callbacks, ``ipywidget`` GUI is HTML based, user
actions, like clicking a button, trigger JavaScript events that are then
translated in to calls to Python code developer registered with the library. It
is a significantly different, asynchronous, paradigm than your basic Jupyter
notebook which operates in a straightforward blocking, linear fashion. It is not
possible to display a Modal UI that would block execution of other Jupyter cells
until needed information is supplied by the user.

``jupyter-ui-poll`` allows one to implement a "blocking GUI" inside a Jupyter
environment. It is a common requirement to query user for some non-trivial input
parameters that are easier to enter via GUI rather than code. User input happens
at the top of the notebook, then that data is used in cells below. While this is
possible to achieve directly with ``ipywidgets`` it requires teaching the user
to enter all the needed data before moving on to execute the cells below. This
is bound to cause some confusion and also breaks ``Cells -> Run All`` functionality.

An obvious solution is to keep running in a loop until all the needed data was
entered by the user.

.. code-block:: python

   display(app.make_ui())
   while not app.have_all_the_data():
       time.sleep(0.1)

A naive version of the code above does not work. This is because no widget
events are being processed while executing code inside a Jupyter cell. Callbacks
you have registered with the widget library won't get a chance to run and so
state of ``app.have_all_the_data()`` won't ever change. "Execute code inside
Jupyter cell" is just another event being processed by the IPython kernel, and
only one event is executed at a time. One could ask IPython kernel to process
more events by calling ``kernel.do_one_iteration()`` in the poll loop. This
kinda works, callbacks will be called as input is entered, but IPython will also
process "execute cell" events, so ``Cells -> Run All`` scenario will still be
broken, as code in lower cells will be executed before the data it operates on
becomes available.

This library hooks into IPython internal machinery to selectively execute events
in a polling fashion, delaying code cell execution events until after
interactive part is over.

Basic idea was copied from ``ipython_blocking`` [#]_ project:

1. Overwrite ``execute_request`` handler in IPython kernel temporarily
2. Call ``kernel.do_one_iteration()`` in a polling fashion until exit conditions are met
3. Reinstate default handler for ``execute_request``
4. Replay code cell execution events cached by custom handler taking care of
   where output goes, and being careful about exception handling


.. [#] https://jupyter.org/
.. [#] https://github.com/jupyter-widgets/ipywidgets
.. [#] https://github.com/kafonek/ipython_blocking

.. _Example notebook : notebooks/Examples.ipynb
.. _run it : https://mybinder.org/v2/gh/kirill888/jupyter-ui-poll/develop?filepath=notebooks%2FExamples.ipynb
.. _Binder : https://mybinder.org/

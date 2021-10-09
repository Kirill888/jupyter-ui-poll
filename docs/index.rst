jupyter-ui-poll
===============

Block Jupyter cell execution while interacting with widgets_.

This library is for people familiar with :mod:`ipywidgets` who want to solve the
following problem:

1. Display User Interface in Jupyter using :mod:`ipywidgets` or similar
2. Wait for data to be entered (this step is surprisingly non-trivial to implement)
3. Use entered data in cells below

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


.. toctree::
   :hidden:

   install.rst
   api.rst


.. _widgets: https://ipywidgets.readthedocs.io/en/stable/
.. _Example notebook: https://github.com/Kirill888/jupyter-ui-poll/blob/develop/notebooks/Examples.ipynb
.. _run it: https://mybinder.org/v2/gh/kirill888/jupyter-ui-poll/develop?filepath=notebooks%2FExamples.ipynb
.. _Binder: https://mybinder.org/

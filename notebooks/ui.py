""" Sample UI used in the example notebook.
"""
import time
from types import SimpleNamespace
import ipywidgets as w
from IPython.display import display
from jupyter_ui_poll import run_ui_poll_loop


def make_sample_ui(width="600px"):
    """
    Construct sample UI using ipywidgets

    +-------------------------------+
    | Pick your favorite food color |
    | <===progress bar=============>|
    | [b1] [b2] [b3] ..         [bn]|
    | <<<<<<<<< dbg output >>>>>>>>>|
    +-------------------------------+

    Returns object with properties:

      .ui       -- Top level ui container `display(state.ui)`
      .color    -- None initially, set to text when user select color by pressing button
      .progress -- FloatProgress(0, 10)
      .dbg      -- ipywidgets.Output()
    """
    colors = ['lime', 'olive', 'tomato', 'salmon', 'wheat', 'orange', 'plum']

    progress = w.FloatProgress(value=0,
                               min=0,
                               max=1,
                               description='',
                               layout=w.Layout(width='100%'))
    lbl = w.HTML('<center><h2>Pick your favorite food color</h2></center>',
                 layout=w.Layout(width="100%"))

    state = SimpleNamespace(color=None,
                            progress=progress,
                            ui=None,
                            dbg=w.Output())

    def on_btn_click(btn):
        state.color = btn.description
        with state.dbg:
            print("\nClicked {}".format(btn.description))

    def mk_btn(color):
        btn = w.Button(description=color, style=dict(button_color=color))
        btn.on_click(on_btn_click)
        return btn

    state.ui = w.VBox([lbl,
                       progress,
                       w.HBox([mk_btn(color) for color in colors]),
                       state.dbg],
                      layout=w.Layout(width=width, overflow='hidden'))
    return state


def blocking_ui(default='beige', timeout=10):
    """ Displays a UI then blocks until user makes a choice or timeout happens.

        Returns
        =======
         (color, 'user')       if user selects a color in time
         (default, 'timeout')  in case of a timeout
    """
    state = make_sample_ui()

    def poll_cbk():
        """ This function is called periodically.

            - Check for user input
            - Check for timeout
            - Update timeout progress bar

            Returns
            -------
            (color: str, 'user')      -- when user selection detected
            (default: str, 'timeout') -- when no user selection for too long
            None                      -- in all other cases
        """
        if state.color is not None:      # User selected some color
            return state.color, 'user'
        # no action from user so far

        # update progress bar
        progress = state.progress
        progress.value = progress.max*(time.time() - state.t_start)/timeout

        if progress.value > 0.7*progress.max:
            if progress.bar_style != 'danger':
                with state.dbg:
                    print('Hurry!!!')

            progress.bar_style = 'danger'

        if progress.value >= progress.max:
            with state.dbg:
                print("\nTimes UP!")
            return default, 'timeout'    # Terminate -- out of time

        # continue polling
        return None

    display(state.ui)
    state.t_start = time.time()

    # call poll_cbk @ 25 fps,
    # process 4 ui events between calls
    return run_ui_poll_loop(poll_cbk, 1/25, 4)

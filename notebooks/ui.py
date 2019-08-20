import ipywidgets as w
from types import SimpleNamespace


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
      .color    -- None set to text when user select color by pressing button
      .progress -- FloatProgress(0, 10)
      .dbg      -- Output()
    """
    colors=['lime', 'olive', 'tomato', 'salmon', 'wheat', 'orange', 'plum']

    progress = w.FloatProgress(value=0, min=0, max=10,
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
        b = w.Button(description=color,
                     style=dict(button_color=color))
        b.on_click(on_btn_click)
        return b

    state.ui = w.VBox([lbl,
                       progress,
                       w.HBox([mk_btn(color) for color in colors]),
                       state.dbg],
                      layout=w.Layout(width=width,
                                      overflow='hidden'))
    return state

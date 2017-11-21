import os
from os.path import join as joinp

import ipywidgets as widgets
import matplotlib.pyplot as plt
import numpy as np
from IPython.display import display
from matplotlib.cm import get_cmap
from mpl_toolkits.axes_grid1 import SubplotDivider, LocatableAxes
from mpl_toolkits.axes_grid1.axes_size import Scaled

from .utils import (
    load_test_data,
    get_layer_dims,
    get_epochs,
    get_pattern_options,
    get_layer_names
)


class Observer(object):
    def __init__(self, img, gax):
        self.fig = img.figure
        self.ax = img.axes
        self.img = img
        self.gax = gax
        self.fig.canvas.mpl_connect('motion_notify_event', self)

    def __call__(self, event):
        if event.inaxes == self.ax:
            val = self.img.get_cursor_data(event)
            self.update_label(val)
            self.fig.canvas.draw_idle()
        elif event.inaxes == self.gax:
            self.clear_label()
            self.fig.canvas.draw_idle()

    def update_label(self, val):
        self.gax.set_xlabel('{:.4f}'.format(val))

    def clear_label(self):
        self.gax.set_xlabel('')


def _make_logs_widget(log_path, layout):
    filenames = [filename for filename in os.listdir(log_path) if '.pkl' in filename]
    runlogs = {}
    for filename in filenames:
        runlogs[filename] = joinp(log_path, filename)
    run_widget = widgets.Dropdown(
        options=runlogs,
        description='Run log: ',
        value=runlogs[filenames[0]],
        layout=layout
    )
    return run_widget


def _make_ghost_axis(mpl_figure, rect, title):
    ghost_ax = mpl_figure.add_axes(rect)
    [ghost_ax.spines[side].set_visible(False) for side in ['right','top','bottom','left']]
    ghost_ax.set_xticks([])
    ghost_ax.set_yticks([])
    ghost_ax.set_ylabel(title)
    ghost_ax.xaxis.set_label_coords(1, 0)
    return ghost_ax


def _make_axes_grid(mpl_figure, N, subplot_ind, layer_name, inp_size, layer_size, mode, target=False):
    '''
    DOCUMENTATION
    :param mpl_figure: an instance of matplotlib.figure.Figure
    :param N: number of layers
    :param i: layer index
    :param inp_size: number units in the layer
    :param layer_size: number of sending units to the layer
    :param target: include target
    :return:
    '''

    # provide axes-grid coordinates, image sizes, and titles
    t = int(target)
    ax_params = {
        'input_': ((0, 0), (1, inp_size), 'input'),
        'weights': ((0, 2), (layer_size, inp_size), 'W'),
        'biases': ((2, 2), (layer_size, 1), 'b'),
        'net_input': ((4, 2), (layer_size, 1), 'net'),
        'output': ((6, 2), (layer_size, 1), 'a')
    }
    if t: ax_params['targets'] = ((8, 2), (layer_size, 1), 't')

    # define padding size
    _ = Scaled(.8)

    # define grid column sizes (left to right): weights, biases, net_input, output, gweight, gbiases, gnet_input, goutput
    mat_w, cvec_w = Scaled(inp_size), Scaled(1)
    left_panel = [mat_w, _, cvec_w, _, cvec_w, _, cvec_w, _]
    cols =  left_panel + [cvec_w,_] if target else left_panel

    if mode > 0:
        right_panel = [_, mat_w, _, cvec_w, _, cvec_w, _, cvec_w]
        gax_params = {
            'gweights': ((9 + 2 * t, 2), (layer_size, inp_size), 'W\''),
            'gbiases': ((11 + 2 * t, 2), (layer_size, 1), 'b\''),
            'gnet_input': ((13 + 2 * t, 2), (layer_size, 1), 'net\''),
            'goutput': ((15 + 2 * t, 2), (layer_size, 1), 'a\'')
        }
        for k,v in gax_params.items(): ax_params[k] = v
        if mode > 1:
            right_panel += [_, mat_w, _, cvec_w]
            ax_params['sgweights'] = ((17 + 2 * t, 2), (layer_size, inp_size), 'sW\'')
            ax_params['sgbiases'] = ((19 + 2 * t, 2), (layer_size, 1), 'sb\'')
        cols += right_panel

    # define grid row sizes (top to bottom): weights, input
    mat_h, rvec_h = Scaled(layer_size), Scaled(1)
    rows = [rvec_h, _, mat_h]

    # make divider
    divider = SubplotDivider(mpl_figure, N, 1, subplot_ind, aspect=True, anchor='W')
    divider.set_horizontal(cols)
    divider.set_vertical(rows)

    # set suptitle
    gax = _make_ghost_axis(mpl_figure=mpl_figure, rect=divider.get_position(), title=layer_name)

    # create axes and locate appropriately
    img_dict = {}
    for k, (ax_coords, img_dims, ax_title) in ax_params.items():
        ax = LocatableAxes(mpl_figure, divider.get_position())
        ax.set_axes_locator(divider.new_locator(nx=ax_coords[0], ny=ax_coords[1]))
        ax.tick_params(labelbottom=False, labelleft=False)
        ax.set_xticks([]); ax.set_yticks([])
        if k == 'input_':
            ax.set_xlabel(ax_title)
        else:
            ax.set_title(ax_title)
        mpl_figure.add_axes(ax)
        img = ax.imshow(np.zeros(img_dims))
        img_dict[k] = img
        Observer(img, gax)
    return img_dict


def _draw_layers(runlog_path, img_dicts, layer_names, colormap, vrange, tind, pind):

    # pull up required data
    snap_ldicts = {}
    snap = load_test_data(runlog_path=runlog_path)[tind]

    enum = snap['enum']
    loss = snap['loss'][pind]
    targ = snap['target']

    for layer_name in layer_names:
        snap_ldicts[layer_name] = snap[layer_name]
        snap_ldicts[layer_name]['targets'] = targ

    del snap # clean up

    print('epoch {}, loss = {:.5f}'.format(enum, loss))

    for img_dict, layer_name in zip(img_dicts, layer_names):
        for k, img in img_dict.items():
            data = snap_ldicts[layer_name][k]
            if k == 'weights':
                data = data.T
            if 'biases' in k:
                data = np.expand_dims(data, axis=1)
            if data.ndim > 2:
                data = data[pind]
                if k != 'input_':
                    data = data.T
            img.set_data(data)
            img.cmap = get_cmap(colormap)
            img.norm.vmin = vrange[0]
            img.norm.vmax = vrange[1]


def view_layers(log_path, mode=0):
    '''
    DOCUMENTATION
    :param log_path: path to log directory that contains pickled run logs
    :param mode: viewing mode index. Must be an int between 0 and 2
        0: limits the viewing to feedforward information only (weights, biases, net_input, output)
        1: same as 0, but also includes gradient information (gweights, gbiases, gnet_input, goutput)
        2: same as 2, but also includes cumulative gradient information
    :return:
    '''

    _widget_layout = widgets.Layout(width='100%')

    run_widget = _make_logs_widget(log_path=log_path, layout=_widget_layout)
    runlog_path = run_widget.value
    epochs = get_epochs(runlog_path=runlog_path)
    layer_names = get_layer_names(runlog_path=runlog_path)
    layer_dims = get_layer_dims(runlog_path=runlog_path, layer_names=layer_names)

    figure = plt.figure()
    num_layers = len(layer_names)
    axes_dicts = []

    disp_targs = [False for l in layer_names[:-1]] + [True]
    for i, (layer_name, disp_targ) in enumerate(zip(layer_names, disp_targs)):
        axes_dicts.append(
            _make_axes_grid(
                mpl_figure=figure,
                N = num_layers,
                subplot_ind = i,
                layer_name = layer_name.upper().replace('_',' '),
                inp_size= layer_dims[layer_name][0],
                layer_size= layer_dims[layer_name][1],
                mode = mode,
                target = bool(disp_targ))
        )

    cmap_widget = widgets.Dropdown(
        options=sorted(['BrBG', 'bwr', 'coolwarm', 'PiYG',
                        'PRGn', 'PuOr', 'RdBu', 'RdGy',
                        'RdYlBu', 'RdYlGn', 'seismic']),
        description='Colors: ',
        value='coolwarm',
        disabled=False,
        layout = _widget_layout
    )

    vrange_widget = widgets.IntRangeSlider(
        value=[-1, 1],
        min=-5,
        max=5,
        step=.5,
        description='V-range: ',
        continuous_update=False,
        layout = _widget_layout
    )

    step_widget = widgets.IntSlider(
        value=epochs[0],
        min=0,
        max=len(epochs) - 1,
        step=1,
        description='Step index: ',
        continuous_update=False,
        layout = _widget_layout
    )

    pattern_options = get_pattern_options(runlog_path=runlog_path, tind=step_widget.value)
    options_map = {}
    for i, pattern_option in enumerate(pattern_options):
        options_map[pattern_option] = i
    pattern_widget = widgets.Select(
        options=options_map,
        value=0,
        rows=min(10, len(pattern_options)),
        description='Pattern: ',
        disabled=False,
        layout = _widget_layout
    )

    controls_dict = dict(
        runlog_path=run_widget,
        img_dicts=widgets.fixed(axes_dicts),
        layer_names=widgets.fixed(layer_names),
        colormap=cmap_widget,
        vrange=vrange_widget,
        tind=step_widget,
        pind=pattern_widget,
    )

    row_layout = widgets.Layout(
        display = 'flex',
        flex_flow = 'row',
        justify_content = 'center'
    )

    control_panel_rows = [
        widgets.Box(children=[controls_dict['runlog_path'], controls_dict['pind']], layout=row_layout),
        widgets.Box(children=[controls_dict['colormap'], controls_dict['vrange']], layout=row_layout),
        widgets.Box(children=[controls_dict['tind']], layout=row_layout),
    ]

    controls_panel = widgets.Box(
        children=control_panel_rows,
        layout = widgets.Layout(
            display='flex',
            flex_flow='column',
            border='ridge 1px',
            align_items='stretch',
            width='65%'
        )
    )

    widgets.interactive_output(f=_draw_layers, controls=controls_dict)
    display(controls_panel)
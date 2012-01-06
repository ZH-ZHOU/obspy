# -*- coding: utf-8 -*-
"""
Functions to generate benchmark plots from given SU files.

.. versionadded:: 0.5.1

:copyright:
    The ObsPy Development Team (devs@obspy.org)
:license:
    GNU Lesser General Public License, Version 3
    (http://www.gnu.org/copyleft/lesser.html)
"""

from obspy.segy.segy import SUFile, readSU
import StringIO
import math
import matplotlib.pylab as plt
import matplotlib.cm as cm
import numpy as np
import os


def _calcOffset(trace):
    """
    Calculating offset for given trace.
    """
    th = trace.header
    # Some programs out there use the scalco field in an non-standard
    # way. These programs store the scaling factor or divisor in terms
    # of an exponent to the base of 10. This conditional handles these
    # non-standard values.
    scalco = abs(th.scalar_to_be_applied_to_all_coordinates)
    if scalco < 10 and scalco != 1:
        scalco = pow(10, scalco)
    offset = 1.0 / scalco * \
        math.sqrt(pow(th.group_coordinate_x - th.source_coordinate_x, 2) + \
                  pow(th.group_coordinate_y - th.source_coordinate_y, 2))
    return offset


def plotBenchmark(sufiles, normalize='traces', clip_partial_traces=True,
                  scale=3.0, xmin=None, xmax=None, ymin=None, ymax=None,
                  fig=None, plot_legend=True, title="", size=(800, 600),
                  dpi=100, outfile=None, format=None,
                  trim_to_smallest_trace=True):
    """
    Plot a benchmark plot from given SU files.

    :type sufiles: List of SU file names or :class:`~obspy.segy.segy.SUFile`
        objects.
    :param sufiles: SU files to plot.
    :type normalize: ``None``, ``'stream'`` or ``'traces'``, optional
    :param normalize: If ``'stream'`` is given it will normalize per stream.
        The keyword ``'traces'`` normalizes all traces in all streams. ``None``
        will skip normalization. Defaults to ``'traces'``.
    :type clip_partial_traces: bool, optional
    :param clip_partial_traces: Clips traces which are not completely plotted.
        Defaults to ``True``.
    :type trim_to_smallest_trace: bool, optional
    :param trim_to_smallest_trace: Trims all traces to shortest available
        trace. Defaults to ``True``.
    :type plot_legend: bool, optional
    :param plot_legend: If enabled plots a legend generated by given SU files.
        Defaults to ``True``.
    :type title: string, optional
    :param title: Plots a title if given. Disabled by default.
    :type scale: float, optional
    :param scale: Scales all amplitudes by this factor. Defaults to ``3.0``.
    :type xmin: float, optional
    :param xmin: Minimum of time axis.
    :type xmax: float, optional
    :param xmax: Maximum of time axis.
    :type ymin: float, optional
    :param ymin: Minimum of offset axis.
    :type ymax: float, optional
    :param ymax: Maximum of offset axis.
    :type fig: :class:`matplotlib.figure.Figure`
    :param fig: Use an existing matplotlib figure instance.
        Default to ``None``.
    :type size: tuple, optional
    :param size: Size tuple in pixel for the output file. This corresponds
        to the resolution of the graph for vector formats. Defaults to
        ``(800, 800)`` pixel.
    :type dpi: int, optional
    :param dpi: Dots per inch of the output file. This also affects the
        size of most elements in the graph (text, linewidth, ...).
        Defaults to ``100``.
    :type outfile: string, optional
    :param outfile: Output file name. Also used to automatically
        determine the output format. Supported file formats depend on your
        matplotlib backend. Most backends support png, pdf, ps, eps and
        svg. Defaults to ``None``.
    :type format: string, optional
    :param format: Format of the graph picture. If no format is given the
        outfile parameter will be used to try to automatically determine
        the output format. If no format is found it defaults to png output.
        If no outfile is specified but a format is, than a binary
        imagestring will be returned.
        Defaults to ``None``.

    .. versionadded:: 0.5.1

    .. rubric:: Example

    The following example plots five seismic unix files in one benchmark image.

    >>> import glob
    >>> sufiles = glob.glob('seismic01_*_vz.su')
    >>> from obspy.segy.benchmark import plotBenchmark
    >>> plotBenchmark(sufiles, title="Homogenous halfspace")  # doctest: +SKIP

    .. plot::

        from obspy.core.util import getExampleFile
        files = [getExampleFile('seismic01_fdmpi_vz.su'),
                 getExampleFile('seismic01_gemini_vz.su'),
                 getExampleFile('seismic01_sofi2D_transformed_vz.su'),
                 getExampleFile('seismic01_specfem_vz.su')]
        from obspy.segy.segy import readSU
        from obspy.segy.benchmark import plotBenchmark
        sufiles = [readSU(file) for file in files]
        plotBenchmark(sufiles, title="Homogenous halfspace", xmax=0.14)
    """
    if not sufiles:
        return

    # ensure we have SUFile objects
    streams = []
    for sufile in sufiles:
        if isinstance(sufile, SUFile):
            streams.append(sufile)
        else:
            streams.append(readSU(sufile))

    # get delta from first trace only and assume it for all traces
    delta = streams[0].traces[0].header.sample_interval_in_ms_for_this_trace

    # trim to smallest trace
    if trim_to_smallest_trace:
        # search smallest trace
        npts = []
        for st in streams:
            npts.append(min([len(tr.data) for tr in st.traces]))
        npts = min(npts)
        # trim all traces to max_npts
        for st in streams:
            for tr in st.traces:
                tr.data = tr.data[0:npts]

    # get offsets
    offsets = []
    for st in streams:
        temp = []
        for tr in st.traces:
            temp.append(_calcOffset(tr))
        offsets.append((max(temp) - min(temp)) / len(st.traces))
    min_offset = min(offsets)

    # normalize
    if normalize != 'stream':
        maximums = []
        minimums = []
        for st in streams:
            maximums.append(max([_i.data.max() for _i in st.traces]))
            minimums.append(min([_i.data.min() for _i in st.traces]))
        minimum = min(minimums)
        maximum = max(maximums)
        data_range = maximum - minimum
    for st in streams:
        if normalize == 'stream':
            data_range = max([_i.data.max() for _i in st.traces]) - \
                         min([_i.data.min() for _i in st.traces])
        for tr in st.traces:
            if normalize == 'traces':
                data_range = tr.data.max() - tr.data.min()
            data_range = abs(data_range)
            tr.data /= (data_range / (min_offset * scale))

    # Setup the figure if not passed explicitly.
    if not fig:
        # Setup figure and axes
        _fig = plt.figure(num=None, dpi=dpi, figsize=(float(size[0]) / dpi,
                                                      float(size[1]) / dpi))
        # XXX: Figure out why this is needed sometimes.
        # Set size and dpi.
        _fig.set_dpi(dpi)
        _fig.set_figwidth(float(size[0]) / dpi)
        _fig.set_figheight(float(size[1]) / dpi)
        # set title
        if title:
            if '\n' in title:
                title, subtitle = title.split('\n', 1)
                _fig.suptitle(title, y=0.97)
                _fig.suptitle(subtitle, y=0.935, fontsize='x-small')
            else:
                _fig.suptitle(title, y=0.95)
    else:
        _fig = fig

    # get current axis
    ax = _fig.gca()

    # labels - either file names or stream numbers
    try:
        labels = [os.path.basename(trace.file.name) for trace in streams]
    except:
        labels = ['Stream #' + str(i) for i in range(len(streams))]

    # colors - either auto generated or use a preset
    if len(streams) > 5:
        colors = cm.get_cmap('hsv', len(streams))
        colors = [colors[i] for i in len(streams)]
    else:
        colors = ['grey', 'red', 'green', 'blue', 'black']

    # set first min and max
    min_y = np.Inf
    max_y = -np.Inf
    max_x = -np.Inf

    # plot
    for _i, st in enumerate(streams):
        color = colors[_i]
        legend = True
        for _j, tr in enumerate(st.traces):
            # calculating offset for each trace
            offset = _calcOffset(tr)
            # create x and y arrays
            y = (tr.data) + offset
            x = np.arange(len(tr.data)) * delta / 1000000.
            # get boundaries
            if max(y) > max_y:
                max_y = max(y)
            if min(y) < min_y:
                min_y = min(y)
            if max(x) > max_x:
                max_x = max(x)
            # test if in image
            if clip_partial_traces:
                if ymin is not None and min(y) < ymin:
                    continue
                if ymax is not None and max(y) > ymax:
                    continue
            # plot, add labels only at new streams
            if legend:
                ax.plot(x, y, color=color, label=labels[_i], lw=0.5)
            else:
                ax.plot(x, y, color=color, lw=0.5)
            legend = False

    # limit offset axis
    spacing = (max_y - min_y) / 50.0
    if ymax is None or ymax > max_y:
        ymax = max_y + spacing
    if ymin is None or ymin < min_y:
        ymin = min_y - spacing
    ax.set_ylim(ymin, ymax)

    # limit time axis
    if xmin is None or xmin < 0:
        xmin = 0
    if xmax is None or xmax > max_x:
        xmax = max_x
    ax.set_xlim(xmin, xmax)

    # axis labels
    ax.set_xlabel('time [s]')
    ax.set_ylabel('offset [m]')

    # add legend
    if plot_legend:
        plt.legend(loc=4, bbox_to_anchor=(0, 0.1, 0.9, 1),
                   bbox_transform=plt.gcf().transFigure)
        try:
            leg = plt.gca().get_legend()
            ltext = leg.get_texts()
            plt.setp(ltext, fontsize='x-small')
        except:
            pass

    # handle output
    if outfile is None:
        # Return an binary imagestring if not outfile but format.
        if format:
            imgdata = StringIO.StringIO()
            _fig.savefig(imgdata, format=format, dpi=dpi)
            imgdata.seek(0)
            return imgdata.read()
        elif fig is None:
            plt.show()
        else:
            return fig
    else:
        # If format is set use it.
        if format:
            _fig.savefig(outfile, format=format, dpi=dpi)
        # Otherwise use format from self.outfile or default to PNG.
        else:
            _fig.savefig(outfile, dpi=dpi)


if __name__ == '__main__':
    import doctest
    doctest.testmod(exclude_empty=True)

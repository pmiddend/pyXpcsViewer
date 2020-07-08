import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
from xpcs_fitting import fit_xpcs, fit_tau
from file_locator import FileLocator
from mpl_cmaps_in_ImageItem import pg_get_cmap
from hdf_to_str import get_hdf_info
from hdf_reader import read_file
from PyQt5 import QtCore

import os
import h5py


def get_min_max(data, min_percent=0, max_percent=100, **kwargs):
    vmin = np.percentile(data.ravel(), min_percent)
    vmax = np.percentile(data.ravel(), max_percent)

    if 'plot_norm' in kwargs and 'plot_type' in kwargs:
        if kwargs['plot_norm'] == 3:
            if kwargs['plot_type'] == 'log':
                t = max(abs(vmin), abs(vmax))
                vmin, vmax = -t, t
            else:
                t = max(abs(1 - vmin), abs(vmax - 1))
                vmin, vmax = 1 - t, 1 + t

    return vmin, vmax


def norm_saxs_data(Iq, q, plot_norm=0, plot_type='log'):
    ylabel = 'I'
    if plot_norm == 1:
        Iq = Iq * np.square(q)
        ylabel = ylabel + 'q^2'
    elif plot_norm == 2:
        Iq = Iq * np.square(np.square(q))
        ylabel = ylabel + 'q^4'
    elif plot_norm == 3:
        baseline = Iq[0]
        Iq = Iq / baseline
        ylabel = ylabel + '/I_0'

    if plot_type == 'log':
        Iq = np.log10(Iq)
        ylabel = '$log(%s)$' % ylabel
    else:
        ylabel = '$%s$' % ylabel

    xlabel = '$q (\\AA^{-1})$'
    return Iq, xlabel, ylabel


def create_slice(arr, cutoff):
    id = arr <= cutoff
    end = np.argmin(id)
    if end == 0 and arr[-1] < cutoff:
        end = len(arr)
    return slice(0, end)


class DataLoader(FileLocator):
    def __init__(self, path):
        super().__init__(path)
        # self.target_list
        self.g2_cache = {
            'num_points': None,
            'hash_val': None,
            'res': None,
            'plot_condition': tuple([None, None, None]),
            'fit_val': {}
        }

    def hash(self, max_points=10):
        if self.target_list is None:
            return hash(None)
        elif max_points <= 0:   # use all items
            val = hash(tuple(self.target_list))
        else:
            val = hash(tuple(self.target_list[0: max_points]))
        return val

    def get_hdf_info(self, fname):
        return get_hdf_info(self.cwd, fname)

    def get_g2_data(self, max_points=10, max_q=1.0, max_tel=1e8):
        labels = ['Iq', 'g2', 'g2_err', 't_el', 'ql_sta', 'ql_dyn']
        file_list = self.target_list

        hash_val = self.hash(max_points)
        if self.g2_cache['hash_val'] == hash_val:
            res = self.g2_cache['res']
        else:
            res = self.read_data(labels, file_list[0: max_points])
            self.g2_cache['hash_val'] = hash_val
            self.g2_cache['res'] = res

        tslice = create_slice(res['t_el'][0], max_tel)
        qslice = create_slice(res['ql_dyn'][0], max_q)

        tel = res['t_el'][0][tslice]
        qd = res['ql_dyn'][0][qslice]
        g2 = res['g2'][:, tslice, qslice]
        g2_err = res['g2_err'][:, tslice, qslice]

        return tel, qd, g2, g2_err

    def plot_g2_initialize(self, mp_hdl, num_fig, num_points, num_col=4):
        # adjust canvas size according to number of images
        num_row = (num_fig + num_col - 1) // num_col

        canvas_size = max(600, 200 * num_row)
        mp_hdl.setMinimumSize(QtCore.QSize(0, canvas_size))
        mp_hdl.fig.clear()
        mp_hdl.subplots(num_row, num_col)
        mp_hdl.obj = None

        # dummy x y fit line
        x = np.logspace(-5, 0, 32)
        y = np.exp(-x / 1E-3) * 0.25 + 1.0
        err = y / 40

        err_obj = []
        lin_obj = []

        for idx in range(num_points):
            for i in range(num_fig):
                offset = 0.03 * idx
                ax = mp_hdl.axes.ravel()[i]
                obj1 = ax.errorbar(x, y + offset,
                                   yerr=err, fmt='o', markersize=3,
                                   markerfacecolor='none',
                                   label='{}'.format(self.id_list[idx]))
                err_obj.append(obj1)

                obj2 = ax.plot(x, y + offset)
                lin_obj.append(obj2)

                # last image
                if idx == num_points - 1:
                    # ax.set_title('Q = %5.4f $\AA^{-1}$' % ql_dyn[i])
                    ax.set_xscale('log')
                    ax.yaxis.set_major_formatter(FormatStrFormatter('%.2f'))
                    # if there's only one point, do not add title; the title
                    # will be too long.
                    if idx >= 1:
                        ax.legend(fontsize=8)

        mp_hdl.fig.tight_layout()
        mp_hdl.obj = {
            'err': err_obj,
            'lin': lin_obj,
        }

    def plot_g2(self, max_q=0.016, max_tel=1E8, handler=None, offset=None,
                max_points=3, bounds=None):

        if len(self.target_list) < 1:
            return ['No target files selected.']

        num_points = min(len(self.target_list), max_points)
        new_condition = (tuple(self.target_list[:num_points]),
                         (max_q, max_tel, offset),
                         bounds)
        if self.g2_cache['plot_condition'] == new_condition:
            return ['No target files selected or change in setting.']
        else:
            cmp = tuple(i != j for i, j in
                        zip(new_condition, self.g2_cache['plot_condition']))
            self.g2_cache['plot_condition'] = new_condition
            plot_target = 4 * cmp[0] + 2 * cmp[1] + cmp[2]

        tel, qd, g2, g2_err = self.get_g2_data(max_q=max_q, max_tel=max_tel,
                                               max_points=max_points)
        num_fig = g2.shape[2]

        if plot_target >= 2 or handler.axes is None:
            self.plot_g2_initialize(handler, num_fig, num_points, 4)
            handler.draw()

        err_msg = []
        for ipt in range(num_points):
            fit_res, fit_val = fit_xpcs(tel, qd, g2[ipt], g2_err[ipt], 
                                        b=bounds)
            self.g2_cache['fit_val'][self.target_list[ipt]] = fit_val
            offset_i = -1 * offset * (ipt + 1)
            err_msg.append(self.target_list[ipt])
            prev_len = len(err_msg)
            for ifg in range(num_fig):
                loc = ipt * num_fig + ifg
                handler.update_lin(loc, fit_res[ifg]['fit_x'],
                                   fit_res[ifg]['fit_y'] + offset_i)
                msg = fit_res[ifg]['err_msg']
                if msg is not None:
                    err_msg.append('----' + msg)

                if plot_target >= 2:
                    handler.update_err(loc, tel, g2[ipt][:, ifg] + offset_i,
                                       g2_err[ipt][:, ifg])

            if len(err_msg) == prev_len:
                err_msg.append('---- fit finished without errors')

        handler.auto_scale()
        handler.draw()
        return err_msg

    def plot_tauq(self, max_q=0.016, hdl=None, offset=None):
        num_points = len(self.g2_cache['fit_val'])
        if num_points == 0:
            return
        labels = self.g2_cache['fit_val'].keys()

        # prepare fit values
        fit_val = []
        for _, val in self.g2_cache['fit_val'].items():
            fit_val.append(val)
        fit_val = np.hstack(fit_val).swapaxes(0, 1)
        q = fit_val[::7]
        sl = q[0] <= max_q

        tau = fit_val[1::7] * 1E4
        cts = fit_val[3::7]

        tau_err = fit_val[4::7] * 1E4
        cts_err = fit_val[6::7]

        if True:
        # if hdl.axes is None:
            hdl.clear()
            ax = hdl.subplots(1, 1)
            line_obj = []
            # for n in range(tau.shape[0]):
            for n in range(tau.shape[0]):
                s = 10 ** (offset * n)
                line = ax.errorbar(q[n][sl], tau[n][sl] / s,
                                   yerr=tau_err[n][sl] / s,
                                   fmt='o-', markersize=3,
                                   label=self.id_list[n]
                                   )
                line_obj.append(line)
                slope, intercept, xf, yf = fit_tau(q[n][sl], tau[n][sl],
                                                   tau_err[n][sl])
                line2 = ax.plot(xf, yf / s)
            ax.set_xlabel('$q (\\AA^{-1})$')
            ax.set_ylabel('$\\tau \\times 10^4$')
            ax.legend()
            ax.set_xscale('log')
            ax.set_yscale('log')
            hdl.obj = line_obj
            hdl.draw()

    def get_detector_extent(self, file_list):
        labels = ['ccd_x0', 'ccd_y0', 'det_dist', 'pix_dim', 'X_energy',
                  'xdim', 'ydim']
        res = self.read_data(labels, file_list)
        extents = []
        for n in range(len(file_list)):
            pix2q = res['pix_dim'][n] / res['det_dist'][n] * \
                    (2 * np.pi / (12.398 / res['X_energy'][n]))

            qy_min = (0 - res['ccd_x0'][n]) * pix2q
            qy_max = (res['xdim'][n] - res['ccd_x0'][n]) * pix2q

            qx_min = (0 - res['ccd_y0'][n]) * pix2q
            qx_max = (res['ydim'][n] - res['ccd_y0'][n]) * pix2q
            temp = (qy_min, qy_max, qx_min, qx_max)

            extents.append(temp)

        return extents

    def plot_saxs_2d_mpl(self, mp_hdl=None, scale='log', max_points=8):
        extents = self.get_detector_extent(self.target_list)
        res = self.get_saxs_data()
        ans = res['Int_2D']
        if scale == 'log':
            ans = np.log10(ans + 1E-8)
        num_fig = min(max_points, len(extents))
        num_col = (num_fig + 1) // 2
        ax_shape = (2, num_col)

        if mp_hdl.axes is not None and mp_hdl.axes.shape == ax_shape:
            axes = mp_hdl.axes
            for n in range(num_fig):
                img = mp_hdl.obj[n]
                img.set_data(ans[n])
                ax = axes.flatten()[n]
                ax.set_title(self.id_list[n])
        else:
            mp_hdl.clear()
            axes = mp_hdl.subplots(2, num_col, sharex=True, sharey=True)
            img_obj = []
            for n in range(num_fig):
                ax = axes.flatten()[n]
                img = ax.imshow(ans[n], cmap=plt.get_cmap('jet'),
                                # norm=LogNorm(vmin=1e-7, vmax=1e-4),
                                interpolation=None,
                                extent=extents[n])
                img_obj.append(img)
                ax.set_title(self.id_list[n])
                # ax.axis('off')
            mp_hdl.obj = img_obj
            mp_hdl.fig.tight_layout()
        mp_hdl.draw()

    def plot_saxs_2d(self, pg_hdl, plot_type='log', cmap='jet'):
        ans = self.get_saxs_data()['Int_2D']
        if plot_type == 'log':
            ans = np.log10(ans + 1E-8)
        if True:
            pg_cmap = pg_get_cmap(plt.get_cmap(cmap))
            pg_hdl.setColorMap(pg_cmap)

            if ans.shape[0] > 1:
                xvals = np.arange(ans.shape[0])
                pg_hdl.setImage(ans.swapaxes(1, 2), xvals=xvals)
            else:
                pg_hdl.setImage(ans[0].swapaxes(0, 1))

    def plot_saxs_1d(self, mp_hdl, plot_type='log', plot_norm=0,
                     plot_offset=0, max_points=8):
        num_points = min(len(self.target_list), max_points)
        res = self.get_saxs_data()
        q = res['ql_sta']
        Iq = res['Iq']

        Iq, xlabel, ylabel = norm_saxs_data(Iq, q, plot_norm, plot_type)

        if mp_hdl.shape == (1, 1) and len(mp_hdl.obj) == num_points:
            for n in range(num_points):
                offset = -plot_offset * (n + 1)
                line = mp_hdl.obj[n]
                line.set_data(q[n], Iq[n] + offset)
            mp_hdl.axes.set_ylabel(ylabel)
            mp_hdl.auto_scale()
        else:
            mp_hdl.clear()
            ax = mp_hdl.subplots(1, 1)
            lin_obj = []
            for n in range(num_points):
                offset = -plot_offset * (n + 1)
                line, = ax.plot(q[n], Iq[n] + offset, 'o--', lw=0.5, alpha=0.8,
                                markersize=2, label=self.id_list[n])
                lin_obj.append(line)
            mp_hdl.obj = lin_obj
            mp_hdl.axes.set_ylabel(ylabel)
            mp_hdl.axes.set_xlabel(xlabel)
            ax.legend()
            # do not use tight layout because the ylabel may not display fully.
            # mp_hdl.fig.tight_layout()
        mp_hdl.draw()
        return

    def get_saxs_data(self, max_points=128):
        labels = ['Int_2D', 'Iq', 'ql_sta']
        file_list = self.target_list[0: max_points]
        res = self.read_data(labels, file_list)
        # ans = np.swapaxes(ans, 1, 2)
        # the detector figure is not oriented to image convention;
        return res

    def get_stability_data(self, max_point=50, **kwargs):
        labels = ['Int_t', 'Iq', 'ql_sta']
        res = self.read_data(labels)

        avg_size = (res['Int_t'].shape[2] + max_point - 1) // max_point
        int_t = res['Int_t'][:, 1, :]
        int_t = int_t / np.mean(int_t)
        cum_int = np.cumsum(int_t, axis=1)
        mean_int = np.diff(cum_int[:, ::avg_size]) / avg_size
        res['Int_t'] = mean_int

        q = res["ql_sta"][0]
        Iq, xlabel, ylabel = norm_saxs_data(res["Iq"], q, **kwargs)
        res["Iq_norm"] = Iq

        return res, xlabel, ylabel

    def plot_stability(self, mp_hdl, **kwargs):
        res, xlabel, ylabel = self.get_stability_data(**kwargs)
        ql_sta = res['ql_sta'][0]
        Iq = res['Iq_norm']
        It = res['Int_t']
        It_vmin, It_vmax = get_min_max(It, 1, 99)
        Iq_vmin, Iq_vmax = get_min_max(Iq, 1, 99, **kwargs)

        def add_vline(ax, nums):
            for x in np.arange(nums - 1):
                ax.axvline(x + 0.5, ls='--', lw=0.5, color='black', alpha=0.5)

        def draw_seismic_map(hdl, d0, d1, vmin=None, vmax=None):
            if hdl.axes is None:
                extent = (-0.5, d0.shape[1] - 0.5,
                          np.min(ql_sta), np.max(ql_sta))
                ax = hdl.subplots(2, 1, sharex=False)
                im0 = ax[0].imshow((d0), aspect='auto',
                                   cmap=plt.get_cmap('seismic'),
                                   vmin=It_vmin, vmax=It_vmax,
                                   interpolation=None)

                im1 = ax[1].imshow((d1), aspect='auto',
                                   cmap=plt.get_cmap('seismic'),
                                   vmin=Iq_vmin, vmax=Iq_vmax,
                                   interpolation=None, origin='lower',
                                   extent=extent)

                hdl.fig.colorbar(im0, ax=ax[0])
                hdl.fig.colorbar(im1, ax=ax[1])

                add_vline(ax[0], d0.shape[1])
                add_vline(ax[1], d1.shape[1])

                ax[0].set_title('Intensity / Intensity$_0$')
                ax[0].set_ylabel('segment')

                ax[1].set_ylabel(xlabel)
                ax[1].set_title('SAXS: ' + ylabel)
                ax[1].set_xlabel('frame number')

                # when there are too many points, avoid labeling.
                if d0.shape[1] < 20:
                    ax[1].set_xticks(np.arange(d0.shape[1]))
                    ax[1].set_xticklabels(self.id_list[0: d0.shape[1]])
                hdl.obj = [im0, im1]
                hdl.fig.tight_layout()
            else:
                hdl.obj[0].set_data(d0)
                hdl.obj[1].set_data(d1)

                hdl.obj[0].set_clim(It_vmin, It_vmax)
                hdl.obj[1].set_clim(Iq_vmin, Iq_vmax)
                hdl.axes[1].set_title('SAXS: ' + ylabel)

            hdl.draw()

        draw_seismic_map(mp_hdl, res['Int_t'].T, res['Iq_norm'].T)

    def read_data(self, labels, file_list=None, mask=None):
        if file_list is None:
            file_list = self.target_list

        if mask is None:
            mask = np.ones(shape=len(file_list), dtype=np.bool)

        data = []
        for n, fn in enumerate(file_list):
            if mask[n]:
                data.append(read_file(labels, fn, self.cwd))

        np_data = {}
        for n, label in enumerate(labels):
            temp = [x[n] for x in data]
            np_data[label] = np.array(temp)

        return np_data

    def average(self, baseline=1.03, chunk_size=256):
        labels = ['Iq', 'g2', 'g2_err', 'Int_2D']
        g2 = self.read_data(['g2'], self.target_list)['g2']
        mask = np.mean(g2[:, -10:, 1], axis=1) < baseline

        steps = (len(mask) + chunk_size - 1) // chunk_size
        result = {}
        for n in range(steps):
            beg = chunk_size * (n + 0)
            end = chunk_size * (n + 1)
            end = min(len(mask), end)
            slice0 = slice(beg, end)
            values = self.read_data(labels, file_list=self.target_list[slice0],
                                    mask=mask[slice0])
            if n == 0:
                for label in labels:
                    result[label] = np.sum(values[label], axis=0)
            else:
                for label in labels:
                    result[label] += np.sum(values[label], axis=0)

        num_points = np.sum(mask)
        for label in labels:
            result[label] = result[label] / num_points

        return result


if __name__ == "__main__":
    flist = os.listdir('./data')
    dv = DataLoader('./data', flist)
    dv.average()
    # dv.plot_g2()

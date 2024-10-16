import h5py
import os
import numpy as np
import json
import logging
from .ftype_utils import get_ftype


logger = logging.getLogger(__name__)

key_fname = "default.json"

# if no such file; then use 8idi configure
# if not os.path.isfile(key_fname):
# TODO: force update the configure file; 
if False:
    from .aps_8idi import key as aps_8idi_key
    with open(key_fname, 'w') as f:
        json.dump(aps_8idi_key, f, indent=4)
    logger.info('no key configuration files found; using APS-8IDI')

with open(key_fname) as f:
    try:
        hdf_key = json.load(f)
    except json.JSONDecodeError as e:
        logger.info('default.json in .xpcs_viewer is damaged. %s', e)
        from .aps_8idi import key as aps_8idi_key
        hdf_key = aps_8idi_key


# colors and symbols for plots
colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k']
symbols = ['o', 's', 't', 'd', '+']


def put(save_path, result, ftype='legacy', mode='raw'):
    with h5py.File(save_path, 'a') as f:
        for key, val in result.items():
            if mode == 'alias':
                key = hdf_key[ftype][key]
            if key in f:
                del f[key]
            if isinstance(val, np.ndarray) and val.ndim == 1:
                val = np.reshape(val, (1, -1))
            f[key] = val
        return


def get_abs_cs_scale(fname, ftype='legacy'):
    key = hdf_key[ftype]['abs_cross_section_scale']
    with h5py.File(fname, 'r') as f:
        if key not in f:
            return None
        else:
            return float(f[key][()])


def get(fname, fields, mode='raw', ret_type='dict', ftype='legacy'):
    """
    get the values for the various keys listed in fields for a single
    file;
    :param fname:
    :param fields_raw: list of keys [key1, key2, ..., ]
    :param mode: ['raw' | 'alias']; alias is defined in .hdf_key
                 otherwise the raw hdf key will be used
    :param ret_type: return dictonary if 'dict', list if it is 'list'
    :return: dictionary or dictionary;
    """
    ret = {}

    with h5py.File(fname, 'r') as HDF_Result:
        for key in fields:
            if mode == 'alias':
                if ftype not in hdf_key:
                    raise ValueError(f"cannot find {ftype} in HDF5 key config")
                if key not in hdf_key[ftype]:
                    raise ValueError(f"cannot find {key} in {hdf_key[ftype]}")
                key2 = hdf_key[ftype][key]
            elif mode == 'raw':
                key2 = key
            else:
                raise ValueError("mode not supported.")

            if key2 not in HDF_Result:
                logger.error('key not found: %s', key2)
                raise ValueError('key not found: %s', key2)
            elif 'C2T_all' in key2:
                # C2T_allxxx has to be converted by numpy.array
                val = np.array(HDF_Result.get(key2))
            else:
                val = HDF_Result.get(key2)[()]

            if type(val) == np.ndarray:
                # get rid of length=1 axies;
                if key not in ['g2_full', 'g2_partials',
                               'ql_dyn', 'ql_sta']:
                    val = np.squeeze(val)
                # ql_dyn and ql_sta must be an array, even there's only one
                # element
                # if key in ['ql_dyn', 'ql_sta']:
                #     val = val[0]

            elif type(val) in [np.bytes_, bytes]:
                # converts bytes to unicode;
                val = val.decode()
            ret[key] = val

    if ret_type == 'dict':
        return ret
    elif ret_type == 'list':
        return [ret[key] for key in fields]
    else:
        raise TypeError('ret_type not support')


def get_type(fname):
    ftype = get_ftype(fname)
    try:
        ret = get(fname, ['type'], mode='alias', ftype=ftype)['type']
        ret = ret.capitalize()
    except:
        ret = None
    return ret


def create_id(fname):
    x = os.path.basename(fname)
    idx_1 = x.find('_')
    idx_2 = x.rfind('_', 0, len(x))
    idx_3 = x.rfind('_', 0, idx_2)
    ret = x[0: idx_1] + x[idx_3: idx_2]
    return ret


if __name__ == '__main__':
    pass

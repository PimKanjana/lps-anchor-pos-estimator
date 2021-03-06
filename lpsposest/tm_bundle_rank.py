#
#    ||          ____  _ __
# +------+      / __ )(_) /_______________ _____  ___
# | 0xBC |     / __  / / __/ ___/ ___/ __ `/_  / / _ \
# +------+    / /_/ / / /_/ /__/ /  / /_/ / / /_/  __/
#  ||  ||    /_____/_/\__/\___/_/   \__,_/ /___/\___/
#
#
# LPS Anchor Position Estimator
#
# Copyright (C) 2016 Bitcraze AB
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,USA
#
import numpy as np
from calcresandjac import calcresandjac
from compactionmatrix import compactionmatrix
from numpy import concatenate
from numpy import linalg
from numpy import ones
from numpy import ravel_multi_index
from numpy import zeros
from scipy.sparse import csr_matrix
from updatexy import updatexy


class structtype():
    pass


def tm_bundle_rank(sol, d):
    r_c = (sol.Bhat).shape
    mm = r_c[0]
    nn = r_c[1]

    cl, dl = compactionmatrix(mm)
    cr, dr = compactionmatrix(nn)

    d2 = d ** 2

    d2shuffle = d2[sol.rows, sol.cols]
    ishuffle = sol.inlmatrix[sol.rows, sol.cols]
    I, J = (ishuffle == 1).nonzero()
    V = (np.array(range(1, np.size(I) + 1))).conj().T

    d2vm = d2shuffle[ravel_multi_index(
        (I, J), dims=d2shuffle.shape, order='F')]

    ineededinBhat = ishuffle == 1
    ineededinBhat[:, 1] = ones(mm, 1)
    ineededinBhat[1, :] = ones(1, nn)
    (I2, J2) = np.where(ineededinBhat != 0)

    ord1 = (J2 == 1).nonzero()
    ord2 = (I2 == 1 and J2 > 1).nonzero()
    ord3 = (I2 > 1 and J2 > 1).nonzero()
    I2 = I2[(concatenate((ord1, ord2, ord3)))]
    J2 = J2[(concatenate((ord1, ord2, ord3)))]
    nspecial = len(ord1) + len(ord2)
    nrest = len(ord3)
    I22 = I2[(nspecial + 1):(nspecial + nrest)] - 1
    J22 = J2[(nspecial + 1):(nspecial + nrest)] - 1
    V2 = range(1, len(I2) + 1)
    ij2v = csr_matrix((V2, (I2, J2)), shape=(mm, nn)).toarray()

    II = V
    JJ = ij2v[ravel_multi_index((I, J), dims=ij2v.shape, order='F')]

    sel1 = (I > 1).nonzero()
    II = concatenate((II, V[sel1]))
    JJ = concatenate((JJ, ij2v[ravel_multi_index(
        (ones(sel1.shape, J[sel1])), dims=ij2v.shape, order='F')]))

    sel2 = (J > 1).nonzero()
    II = concatenate((II, V[sel2]))
    JJ = concatenate((JJ, ij2v[ravel_multi_index(
        (I[sel2], ones(sel2.shape)), dims=ij2v.shape, order='F')]))

    sel3 = np.where((J > 1) and (I > 1))
    II = concatenate((II, V[sel3]))
    JJ = concatenate((JJ, ij2v[ravel_multi_index(
        (ones(sel3.shape), ones(sel3.shape)), dims=ij2v.shape, order='F')]))

    bhat2d2 = csr_matrix((ones(II.shape), (II, JJ)),
                         shape=(len(V), len(V2))).toarray()

    Bhat = sol.Bhat

    u, s, vh = linalg.svd(Bhat[2:, 2:])
    v = vh.T

    U = u[:, 0:2]
    V = s[0:2, 0:2] * v[:, 0:2]
    R = Bhat[ravel_multi_index(
        (I2[0:nspecial], J2[0:nspecial]), dims=Bhat.size, order='F')]

    Uchange = ones(U.shape)
    Uchange[0:2, 0:2] = zeros(3, 3)
    (iu, ju) = Uchange.nonzero()
    indu = ravel_multi_index((iu, ju), dims=U.shape, order='F')

    Vchange = ones(V.shape)
    (iv, jv) = Vchange.nonzero()
    indv = ravel_multi_index((iu, ju), dims=V.shape, order='F')

    nzr = len(R)
    nzu = Uchange.sum()
    nzv = Vchange.sum()

    indzr = range(1, nzr + 1)
    indzu = range(nzr + 1, nzr + nzu + 1)
    indzv = range(nzr + nzu + 1, nzr + nzu + nzv + 1)

    param = structtype()
    param.U = U
    param.V = V
    param.R = R
    param.indu = indu
    param.indv = indv
    param.indzr = indzr
    param.indzu = indzu
    param.indzv = indzv
    param.nzr = nzr
    param.mm = mm
    param.nn = nn

    mdata = structtype()
    mdata.d2vm = d2vm
    mdata.bhat2d2 = bhat2d2
    mdata.I22 = I22
    mdata.J22 = J22

    debug = 0

    res0, jac0 = calcresandjac(mdata, param)

    res = None
    for kkk in range(0, 5):

        res, jac = calcresandjac(mdata, param)

        dz = -(linalg.solve(jac, res))

        param_new = updatexy(param, dz)
        res2, jac2 = calcresandjac(mdata, param_new)
        aa = concatenate((linalg.norm(res), linalg.norm(
            res + jac * dz), linalg.norm(res2)), 1)
        bb = aa
        bb = bb - bb[1]
        bb = bb / bb[0]
        cc = linalg.norm(jac * dz) / linalg.norm(res)

        if linalg.norm(res) < linalg.norm(res2):

            if cc > 0.0001:

                kkkk = 1
                while (kkkk < 50) and (
                        linalg.norm(res) < linalg.norm(res2)):
                    dz = dz / 2
                    param_new = updatexy(param, dz)
                    res2, jac2 = calcresandjac(mdata, param_new)
                    kkkk = kkkk + 1

        if debug:
            aa = concatenate((linalg.norm(res), linalg.norm(
                res + jac * dz), linalg.norm(res2)), 1)
            bb = aa
            bb = bb - bb[1]
            bb = bb / bb[0]
            cc = linalg.norm(jac * dz) / linalg.norm(res)

            print(aa, bb, cc)

        if linalg.norm(res2) < linalg.norm(res):
            param = param_new

    param_opt = param

    BB = zeros((mm, nn))
    BB[1:, 1:] = (param_opt.U).conj().T * param_opt.V
    matsize = Bhat.shape
    rowSub = I2[0:nspecial]
    colSub = J2[0:nspecial]

    BB[ravel_multi_index(
        (rowSub, colSub), dims=matsize, order='F')] = param_opt.R
    d2calc = zeros((d.shape))
    d2calc_shuffle = linalg.inv(dl) * BB * linalg.inv((dr.conj().T))
    d2calc[sol.rows, sol.cols] = d2calc_shuffle

    sol.Bhat = BB

    return sol, res0, res, d2calc

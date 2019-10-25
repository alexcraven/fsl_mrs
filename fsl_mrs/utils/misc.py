#!/usr/bin/env python

# misc.py - Various utils
#
# Author: Saad Jbabdi <saad@fmrib.ox.ac.uk>
#
# Copyright (C) 2019 University of Oxford 
# SHBASECOPYRIGHT

import numpy as np
from scipy.signal import butter, lfilter

H2O_PPM_TO_TMS = 4.65  # Shift of water to Tetramethylsilane


# Convention:
#  freq in Hz
#  ppm = freq/1e6
#  ppm_shift = ppm - 4.65
#  why is there a minus sign here? 

def ppm2hz(cf,ppm,shift=True):
    if shift:
        return (ppm-H2O_PPM_TO_TMS)*cf*1E-6
    else:
        return (ppm)*cf*1E-6

def hz2ppm(cf,hz,shift=True):
    if shift:
        return 1E6 *hz/cf + H2O_PPM_TO_TMS
    else:
        return 1E6 *hz/cf

def filter(mrs,FID,ppmlim,filter_type='bandpass'):
    """
       Filter in/out frequencies defined in ppm
       
       Parameters
       ----------
       mrs    : MRS Object
       FID    : array-like
              temporal signal to filter
       ppmlim : float or tuple              
       filter_type: {'lowpass','highpass','bandpass', 'bandstop'}
              default type is 'bandstop')

       Outputs
       -------
       numpy array 
    """
    
    # Sampling frequency (Hz)
    fs     = 1/mrs.dwellTime
    nyq    = 0.5 * fs

    #first,last = mrs.ppmlim_to_range(ppmlim)
    #f1,f2 = np.abs(mrs.frequencyAxis[first]),np.abs(mrs.frequencyAxis[last])
    #if f1>f2:
    #    f1,f2=f2,f1
    #wn = [f1/nyq,f2/nyq]

    f1 = np.abs(ppm2hz(mrs.centralFrequency,ppmlim[0])/ nyq)
    f2 = np.abs(ppm2hz(mrs.centralFrequency,ppmlim[1])/ nyq)

    if f1>f2:
        f1,f2=f2,f1
    wn = [f1,f2]

    #print(wn)
    
    order = 6
    
    b,a = butter(order, wn, btype=filter_type)
    y = lfilter(b, a, FID)
    return y


# Numerical differentiation (light)
import numpy as np
#Gradient Function
def gradient(x, f):
    """
      Calculate f'(x): the numerical gradient of a function

      Parameters:
      -----------
      x : array-like 
      f : scalar function

      Returns:
      --------
      array-like
    """
    x = x.astype(float)
    N = x.size
    gradient = []
    for i in range(N):
        eps = abs(x[i]) *  np.finfo(np.float32).eps 
        if eps==0: 
            eps = 1e-5
        xx0 = 1. * x[i]
        f0 = f(x)
        x[i] = x[i] + eps
        f1 = f(x)
        #gradient.append(np.asscalar(np.array([f1 - f0]))/eps)
        gradient.append((f1-f0)/eps)
        x[i] = xx0
    return np.array(gradient)



#Hessian Matrix
def hessian (x, f):
    """
       Calculate numerical Hessian of f at x
       
       Parameters:
       -----------
       x : array-like
       f : function

       Returns:
       --------
       matrix
    """
    N = x.size
    hessian = np.zeros((N,N)) 
    gd_0 = gradient( x, f)
    eps = np.linalg.norm(gd_0) * np.finfo(np.float32).eps 
    if eps==0: 
        eps = 1e-5
    for i in range(N):
        xx0 = 1.*x[i]
        x[i] = xx0 + eps
        gd_1 =  gradient(x, f)
        hessian[:,i] = ((gd_1 - gd_0)/eps).reshape(x.shape[0])
        x[i] =xx0
    return hessian

def hessian_diag(x,f):
    """
       Calculate numerical second order derivative of f at x
       (the diagonal of the Hessian)
       
       Parameters:
       -----------
       x : array-like
       f : function

       Returns:
       --------
       array-like
    """
    N = x.size
    hess = np.zeros((N,1)) 
    gd_0 = gradient( x, f)    
    eps = np.linalg.norm(gd_0) * np.finfo(np.float32).eps

    if eps==0: 
        eps = 1e-5
    for i in range(N):
        xx0 = 1.*x[i]
        x[i] = xx0 + eps
        gd_1 =  gradient(x, f)
        hess[i] = ((gd_1[i] - gd_0[i])/eps)
        x[i] =xx0

    return hess



# Little bit of code for checking the gradients
def check_gradients():
    m = np.linspace(0,10,100)
    cf = lambda p : np.sum(p[0]*np.exp(-p[1]*m))
    x0 = np.random.randn(2)*.1
    grad_num = gradient(x0,cf)
    E = lambda x : np.sum(np.exp(-x[1]*m))
    grad_anal = np.array([E(x0),-x0[0]*np.sum(m*np.exp(-x0[1]*m))])
    hess_anal = np.zeros((2,2))
    hess_anal[0,1] = -np.sum(m*np.exp(-x0[1]*m))
    hess_anal[1,0] = -np.sum(m*np.exp(-x0[1]*m))
    hess_anal[1,1] = x0[0]*np.sum(m**2*np.exp(-x0[1]*m))
    hess_num = hessian(x0,cf)
    hess_diag = hessian_diag(x0,cf)
    print('x0 = {}, f(x0)  = {}'.format(x0,cf(x0)))
    print('Grad Analytic   : {}'.format(grad_anal))
    print('Grad Numerical  : {}'.format(grad_num))
    print('Hess Analytic   : {}'.format(hess_anal))
    print('Hess Numreical  : {}'.format(hess_num))
    print('Hess Diag       : {}'.format(hess_diag))
    

def calculate_crlb(x,f,data):
    """
       Calculate Cramer-Rao Lower Bound
       This assumes a model of the form data = f(x) + noise
       where noise ~ N(0,sig^2)
       In which case the CRLB is sum( |f'(x)|^2 )/sig^2
       It uses numerical differentiation to get f'(x)

      Parameters:
       x : array-like
       f : function
       data : array-like

      Returns:
        array-like
    """
    # estimate noise variance empirically
    sig2 = np.var(data-f(x))
    grad = gradient(x,f)        
    crlb = 1/(np.sum(np.abs(grad)**2,axis=1)/sig2)
    
    return crlb

def calculate_lap_cov(x,f,data):
    """
       Calculate approximate covariance using
       Fisher information matrix

      Parameters:
       x : array-like
       f : function
       data : array-like

      Returns:
        2D array    
    """
    N = x.size
    C = np.zeros((N,N))

    sig2 = np.var(data-f(x))
    grad = gradient(x,f)
    for i in range(N):
        for j in range(N):
            fij = np.real(grad[i])*np.real(grad[j]) + np.imag(grad[i])*np.imag(grad[j])
            C[i,j] = np.sum(fij)/sig2

    C = np.linalg.pinv(C)
    return C


# Various utilities
def multiply(x,y):
    """
     Elementwise multiply numpy arrays x and y 
     
     Returns same shape as x
    """
    shape = x.shape
    r = x.flatten()*y.flatten()
    return np.reshape(r,shape)

def shift_FID(mrs,FID,eps):
    """
       Shift FID in spectral domain

    Parameters:
       mrs : MRS object
       FID : array-like
       eps : shift factor (Hz)

    Returns:
       array-like
    """
    t = mrs.timeAxis
    FID_shifted = np.fft.ifft(np.fft.fft(multiply(FID,np.exp(-1j*t*eps)),axis=0),axis=0)
    FID_shifted = FID_shifted
    return FID_shifted
 
def blur_FID(mrs,FID,gamma):
    """
       Blur FID in spectral domain

    Parameters:
       mrs   : MRS object
       FID   : array-like
       gamma : blur factor in Hz

    Returns:
       array-like
    """
    t = mrs.timeAxis
    FID_blurred = np.fft.ifft(np.fft.fft(multiply(FID,np.exp(-t*gamma)),axis=0),axis=0)
    return FID_blurred

def extract_spectrum(mrs,FID,ppmlim=(0.2,4.2)):
    """
       Extracts spectral interval
    
    Parameters:
       mrs : MRS object
       FID : array-like
       ppmlim : tuple
       
    Returns:
       array-like
    """
    spec  = np.fft.fft(FID,axis=0)
    first, last = mrs.ppmlim_to_range(ppmlim=ppmlim)
    spec = spec[first:last] 
    return spec
       
def normalise(x,axis=0):
    """
       Devides x by norm of x
    """
    return x/np.linalg.norm(x,axis=axis)

def ztransform(x,axis=0):
    """
       Demeans x and make norm(x)=1
    """
    return (x-np.mean(x,axis=axis))/np.std(x,axis)/np.sqrt(x.size)
    
def correlate(x,y):
    """
       Computes correlation between complex signals x and y
       Uses formula : sum( conj(z(x))*z(y)) where z() is the ztransform
    """
    return np.real(np.sum(np.conjugate(ztransform(x))*ztransform(y)))

def phase_correct(FID):
    """
       Apply phase correction to FID
       ADD PPMLIM!!!!!
    """
    phases = np.linspace(0,2*np.pi,1000)
    x = []
    for phase in phases:
        f = np.real(np.fft.fft(FID*np.exp(1j*phase),axis=0))
        x.append(np.sum(f<0))
    phase = phases[np.argmin(x)]
    return FID*np.exp(1j*phase)    



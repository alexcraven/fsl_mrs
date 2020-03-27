from fsl_mrs.core import MRS
import numpy as np
from fsl_mrs.utils.preproc.general import get_target_FID
from fsl_mrs.utils.misc import extract_spectrum,FIDToSpec

def identifyUnlikeFIDs(FIDList,bandwidth,centralFrequency,sdlimit = 1.96,iterations=2,ppmlim=None,shift=True):
    """ Identify FIDs in a list that are unlike the others

    Args:
        FIDList (list of ndarray): Time domain data
        bandwidth (float)        : Bandwidth in Hz
        centralFrequency (float) : Central frequency in Hz
        sdlimit (float,optional) : Exclusion limit (number of stnadard deviations). Default = 3.
        iterations (int,optional): Number of iterations to use.
        ppmlim (tuple,optional)  : Limit to this ppm range
        shift (bool,optional)    : Apply H20 shft

    Returns:
        goodFIDS (list of ndarray): FIDs that passed the criteria
        badFIDS (list of ndarray): FIDs that failed the likeness critera
        rmIndicies (list of int): Indicies of those FIDs that have been removed
        metric (list of floats): Likeness metric of each FID
    """

    # Calculate the FID to compare to
    target = get_target_FID(FIDList,target='median')

    if ppmlim is not None:
        MRSargs = {'FID':target,'bw':bandwidth,'cf':centralFrequency}
        mrs = MRS(**MRSargs)
        target = extract_spectrum(mrs,target,ppmlim=ppmlim,shift=shift)
        compareList = [extract_spectrum(mrs,f,ppmlim=ppmlim,shift=shift) for f in FIDList]
    else:
        compareList = [FIDToSpec(f) for f in FIDList]
        target = FIDToSpec(target)
    
    # Do the comparison    
    for idx in range(iterations):
        metric = []
        for data in compareList:
            metric.append(np.linalg.norm(data-target))            
        metric = np.asarray(metric)
        metric_avg = np.mean(metric)
        metric_std = np.std(metric)

        goodFIDs,badFIDs,rmIndicies,keepIndicies = [],[],[],[]
        for iDx,(data,m) in enumerate(zip(FIDList,metric)):
            if m > ((sdlimit*metric_std)+metric_avg) or m < (-(sdlimit*metric_std)+metric_avg):
                badFIDs.append(data)
                rmIndicies.append(iDx)
            else:
                goodFIDs.append(data)
                keepIndicies.append(iDx)

        target = get_target_FID(goodFIDs,target='median')
        if ppmlim is not None:
            target = extract_spectrum(mrs,target,ppmlim=ppmlim,shift=shift)
        else:
            target = FIDToSpec(target)
    

    return goodFIDs,badFIDs,keepIndicies,rmIndicies,metric.tolist()


def identifyUnlikeFIDs_report(goodFIDs,badFIDs,hdr,keepIndicies,rmIndicies,metric,ppmlim=(0.2,4.2)):
    from matplotlib import pyplot as plt
    from fsl_mrs.utils.plotting import styleSpectrumAxes
    
    metricGd = np.array(metric)[keepIndicies]
    metricBd = np.array(metric)[rmIndicies]
    gdIndex = np.argsort(metricGd)
    bdIndex = np.argsort(metricBd)

    plotGood,plotBad = [],[]
    toMRSobj = lambda fid : MRS(FID=fid,header=hdr)
    for fid in goodFIDs:
        plotGood.append(toMRSobj(fid))
    for fid in badFIDs:
        plotBad.append(toMRSobj(fid))
        
    target = get_target_FID(goodFIDs,target='median')
    tgtmrs = toMRSobj(target)    
    fig = plt.figure(figsize=(13,10))
    for idx,fid in enumerate(plotGood):
            if idx == 0:
                plt.plot(fid.getAxes(ppmlim=ppmlim),np.real(fid.getSpectrum(ppmlim=ppmlim)),'g',label='Kept')
            else:
                plt.plot(fid.getAxes(ppmlim=ppmlim),np.real(fid.getSpectrum(ppmlim=ppmlim)),'g')
    for idx,fid in enumerate(plotBad):
            if idx == 0:
                plt.plot(fid.getAxes(ppmlim=ppmlim),np.real(fid.getSpectrum(ppmlim=ppmlim)),'r',label='Removed')
            else:
                plt.plot(fid.getAxes(ppmlim=ppmlim),np.real(fid.getSpectrum(ppmlim=ppmlim)),'r')
    plt.plot(tgtmrs.getAxes(ppmlim=ppmlim),np.real(tgtmrs.getSpectrum(ppmlim=ppmlim)),'k',label='Target')
    styleSpectrumAxes(plt.gca())    
    plt.legend()
    plt.show()

    metric_avg = np.mean(metric)
    metric_std = np.std(metric)

    fig = plt.figure(figsize=(13,10))
    ax = plt.gca()
    colourvec = np.arange(0,len(bdIndex))/len(bdIndex)
    colors = plt.cm.Spectral(colourvec)
    ax.set_prop_cycle(color =colors)
    for idx,bdidx in enumerate(bdIndex[::2]):
        metSD = np.abs(metricBd[bdidx]-metric_avg)/metric_std
        plt.plot(plotBad[bdidx].getAxes(ppmlim=ppmlim),np.real(plotBad[bdidx].getSpectrum(ppmlim=ppmlim)),label=f'Removed {idx*2} (SD={metSD:0.2f})')

    metSD = np.abs(metricGd[gdIndex[0]]-metric_avg)/metric_std
    plt.plot(plotGood[gdIndex[0]].getAxes(ppmlim=ppmlim),np.real(plotGood[gdIndex[0]].getSpectrum(ppmlim=ppmlim)),'g',label=f'Kept (SD={metSD:0.2f})')
    plt.plot(tgtmrs.getAxes(ppmlim=ppmlim),np.real(tgtmrs.getSpectrum(ppmlim=ppmlim)),'k',label='Target')
    styleSpectrumAxes(plt.gca())
    plt.legend()
    plt.show()
#!/usr/bin/env python

# fsl_dynmrs - wrapper script for Dynamic MRS fitting
#
# Author: Saad Jbabdi <saad@fmrib.ox.ac.uk>
#         William Clarke <william.clarke@ndcn.ox.ac.uk>
#
# Copyright (C) 2019 University of Oxford
# SHBASECOPYRIGHT

# Quick imports
from pathlib import Path

from fsl_mrs.auxiliary import configargparse
from fsl_mrs import __version__


def main():
    # Parse command-line arguments
    p = configargparse.ArgParser(
        add_config_file_help=False,
        description="FSL Dynamic Magnetic Resonance Spectroscopy Wrapper Script")

    p.add_argument('-v', '--version', action='version', version=__version__)

    required = p.add_argument_group('required arguments')
    fitting_args = p.add_argument_group('fitting options')
    optional = p.add_argument_group('additional options')

    # REQUIRED ARGUMENTS
    required.add_argument('--data',
                          required=True, type=Path, metavar='<FILE>',
                          help='input NIfTI-MRS file (should be 5D NIFTI)')
    required.add_argument('--basis',
                          required=True, type=Path, metavar='<FILE>',
                          help='Basis folder containing basis spectra')
    required.add_argument('--output',
                          required=True, type=Path, metavar='<str>',
                          help='output folder')
    required.add_argument('--dyn_config',
                          required=True, type=Path, metavar='<FILE>',
                          help='configuration file for dynamic fitting')
    required.add_argument('--time_variables',
                          required=True, type=Path, metavar='<FILE>', nargs='+',
                          help='time variable files (e.g. bvals, bvecs, design.mat, etc.)')

    # FITTING ARGUMENTS
    fitting_args.add_argument('--ppmlim', default=(.2, 4.2), type=float,
                              nargs=2, metavar=('LOW', 'HIGH'),
                              help='limit the fit to a freq range'
                                   ' (default=(.2,4.2))')
    fitting_args.add_argument('--h2o', default=None, type=str, metavar='H2O',
                              help='NOT IMPLEMENTED YET - input .H2O file for quantification')
    fitting_args.add_argument('--baseline_order', default=2, type=int,
                              metavar=('ORDER'),
                              help='order of baseline polynomial'
                                   ' (default=2, -1 disables)')
    fitting_args.add_argument('--metab_groups', default=0, nargs='+',
                              type=str_or_int_arg,
                              help='metabolite groups: list of groups'
                                   ' or list of names for indept groups.')
    fitting_args.add_argument('--lorentzian', action="store_true",
                              help='Enable purely lorentzian broadening'
                                   ' (default is Voigt)')

    # ADDITIONAL OPTIONAL ARGUMENTS
    optional.add_argument('--t1', type=str, default=None, metavar='IMAGE',
                          help='structural image (for report)')
    optional.add_argument('--report', action="store_true",
                          help='output html report')
    optional.add_argument('--verbose', action="store_true",
                          help='spit out verbose info')
    optional.add_argument('--overwrite', action="store_true",
                          help='overwrite existing output folder')
    optional.add_argument('--no_rescale', action="store_true",
                          help='Forbid rescaling of FID/basis/H2O.')
    optional.add('--config', required=False, is_config_file=True,
                 help='configuration file')

    # Parse command-line arguments
    args = p.parse_args()

    # ######################################################
    # DO THE IMPORTS AFTER PARSING TO SPEED UP HELP DISPLAY
    import time
    import shutil
    import json
    import warnings
    import matplotlib
    import numpy as np
    matplotlib.use('agg')
    from fsl_mrs.dynamic import dynMRS
    from fsl_mrs.utils import mrs_io
    from fsl_mrs.utils import report
    from fsl_mrs.utils import plotting
    from fsl_mrs.utils import misc
    import datetime
    # ######################################################
    if not args.verbose:
        warnings.filterwarnings("ignore")

    # Check if output folder exists
    overwrite = args.overwrite
    if args.output.is_dir():
        if not overwrite:
            print(f"Folder '{args.output}' exists."
                  " Are you sure you want to delete it? [Y,N]")
            response = input()
            overwrite = response.upper() == "Y"

        if not overwrite:
            print('Please specify a different output folder name.')
            exit()
        else:
            shutil.rmtree(args.output)
            args.output.mkdir(parents=True, exist_ok=True)
    else:
        args.output.mkdir(parents=True, exist_ok=True)

    # Do the work

    # Read data
    if args.verbose:
        print('--->> Read input data\n')
        print(f'  {args.data}')

    data = mrs_io.read_FID(args.data)

    # Display information about the data
    if args.verbose:
        print(f'data shape : {data.shape}')
        print(f'data tags  : {data.dim_tags}')

    if args.h2o is not None:
        raise NotImplementedError("H2O referencing not yet implemented for dynamic fitting.")

    # Create a MRS list
    mrslist = data.mrs(basis_file=args.basis)
    for mrs in mrslist:
        mrs.check_FID(repair=True)
        mrs.check_Basis(repair=True)

    # Get dynmrs time variables
    def load_tvar_file(fp):
        if fp.suffix in ['.csv', ]:
            return np.loadtxt(fp, delimiter=',')
        else:
            return np.loadtxt(fp)

    if len(args.time_variables) == 1:
        time_variables = load_tvar_file(args.time_variables[0])
    else:
        time_variables = [load_tvar_file(v) for v in args.time_variables]

    # Do the fitting here
    if args.verbose:
        print('--->> Start fitting\n\n')
    start = time.time()

    # Parse metabolite groups
    metab_groups = misc.parse_metab_groups(mrslist[0], args.metab_groups)

    # Fitting Arguments
    Fitargs = {'ppmlim': args.ppmlim,
               'baseline_order': args.baseline_order,
               'metab_groups': metab_groups,
               'model': 'voigt'
               }
    if args.lorentzian:
        Fitargs['model'] = 'lorentzian'

    # Now create a dynmrs object
    # This is the main class that knows how to map between
    # the parameters of the MRS model and the parameters
    # of the dynamic model
    if args.verbose:
        print('Creating dynmrs object.')
        print(time_variables)

    dyn = dynMRS(
        mrslist,
        time_variables,
        config_file=args.dyn_config,
        rescale=not args.no_rescale,
        **Fitargs)

    if args.verbose:
        print('Fitting args:')
        print(Fitargs)

    # Initialise the fit
    init = dyn.initialise(verbose=args.verbose)

    # Run dynamic fitting
    dyn_res = dyn.fit(init=init, verbose=args.verbose)

    # QUANTITATION SKIPPED

    # # Combine metabolites. SKIPPED
    # if args.combine is not None:
    #     res.combine(args.combine)
    stop = time.time()

    # Report on the fitting
    if args.verbose:
        duration = stop - start
        print(f'    Fitting lasted          : {duration:.3f} secs.\n')

    # Save output files
    if args.verbose:
        print('--->> Saving output files to {}\n'.format(args.output))

    # Save chosen arguments
    with open(args.output / "options.txt", "w") as f:
        # Deal with stupid non-serialisability of pathlib path objects
        var_print = {}
        for key in vars(args):
            if key in ['data', 'basis', 'output', 'dyn_config']:
                var_print[key] = str(vars(args)[key])
            elif key == 'time_variables':
                var_print['time_variables'] = [str(val) for val in vars(args)['time_variables']]
            else:
                var_print[key] = vars(args)[key]
        f.write(json.dumps(var_print))
        f.write("\n--------\n")
        f.write(p.format_values())

    # dump output to folder
    dyn_res.save(args.output, save_dyn_obj=True)

    # Save image of MRS voxel
    location_fig = None
    if args.t1 is not None \
            and mrslist[0].getXFormCode() > 0:
        fig = plotting.plot_world_orient(args.t1, args.data)
        fig.tight_layout()
        location_fig = args.output / 'voxel_location.png'
        fig.savefig(location_fig, bbox_inches='tight', facecolor='k')

    # Create interactive HTML report
    if args.report:
        t_varFiles = '\n'.join([str(tfile) for tfile in args.time_variables])
        report.create_dynmrs_report(
            dyn_res,
            filename=args.output / 'report.html',
            fidfile=args.data,
            basisfile=args.basis,
            configfile=args.dyn_config,
            tvarfiles=t_varFiles,
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            location_fig=location_fig)

    if args.verbose:
        print('\n\n\nDone.')


def str_or_int_arg(x):
    try:
        return int(x)
    except ValueError:
        return x


if __name__ == '__main__':
    main()
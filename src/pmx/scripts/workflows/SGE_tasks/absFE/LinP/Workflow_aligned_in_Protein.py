#!/usr/bin/env python

import logging
import luigi
import os
#from luigi.contrib.sge import LocalSGEJobTask
from luigi.tools.deps_tree import print_tree
from pmx.scripts.workflows.utils import parse_options
from pmx.scripts.workflows.Workflow import Workflow
from pmx.scripts.workflows.SGE_tasks.absFE.LinP.equil_sims import Sim_PL_NPT
from pmx.scripts.workflows.SGE_tasks.absFE.LinP.alignment import Task_PL_gen_morphes,Task_PL_align
from pmx.scripts.workflows.SGE_tasks.absFE.LinP.TI import Task_PL_TI_simArray


# Scheduler factory that tries to disable reruns
class my_WorkerSchedulerFactory(luigi.interface._WorkerSchedulerFactory):

    def create_local_scheduler(self):
        return luigi.scheduler.Scheduler(prune_on_get_work=True,
                                          record_task_history=False,
                                          retry_count=0)

# Wrapper task that executes requested dependencies
class SGE_test(luigi.task.WrapperTask):

    #avoid Prameter not a string warnings
    job_name_format = luigi.Parameter(
        significant=False, default="", description="A string that can be "
        "formatted with class variables to name the job with qsub.")
    job_name = luigi.Parameter(
        significant=False, default="",
        description="Explicit job name given via qsub.")

    my_deps=[]
    def work(self):
        pass

    def set_deps(self, deps):
        self.my_deps=deps

    def requires(self):
        return( self.my_deps )

# ==============================================================================
#                             Workflow Class
# ==============================================================================
class SGE_Workflow_aligned_in_Protein(Workflow):

    def __init__(self, toppath, mdppath, hosts=[], ligands=[],
                 n_repeats=3, n_sampling_sims=1, basepath=os.getcwd(),
                 d=1.5, bt="dodecahedron", salt_conc=0.15,
                 mdrun="gmx mdrun", mdrun_opts="",
                 b=2256.0):
        Workflow.__init__(self, toppath, mdppath, hosts, ligands,
                          n_repeats, n_sampling_sims, basepath,
                          d, bt, salt_conc, mdrun, mdrun_opts)
        self.states={"A":"l0", "B":"l1"} #states and suffixes of mdp files
        self.TIstates={"A":"l0", "C":"l1"} #states and suffixes of mdp files
        self.b=b

    def gen_folder_name(self,host,ligand):
        return(self.basepath+'/prot_'+host+'/lig_'+ligand)

    def run_everything(self):
        """Runs the whole workflow.

        Parameters
        ----------
        None.

        Returns
        -------
        None.
        """

        #sanity checks
        self.check_sanity()
        self.check_inputs()

        logger = logging.getLogger('luigi-interface')
        logger.setLevel(logging.WARNING)

        self.study_settings={'base_path':self.basepath,
                             'top_path':self.toppath,
                             'mdp_path':self.mdppath,
                             'd':self.d, 'bt':self.bt,
                             'salt_conc':self.salt_conc,
                             'n_repeats':self.n_repeats,
                             'n_sampling_sims':self.n_sampling_sims,
                             'states':self.states,
                             'TIstates':self.TIstates,
                             'mdrun':self.mdrun,
                             'mdrun_opts':self.mdrun_opts,
                             'b':self.b}
        self.tasks=[]

        #TI
        for p in self.hosts:
            for l in self.ligands:
                folder_path = self.gen_folder_name(p,l)
                for sTI in self.TIstates:
                    for i in range(self.n_repeats):
                        for m in range(self.n_sampling_sims):
                            self.tasks.append(Task_PL_TI_simArray(
                                p = p, l = l, i = i, m = m, sTI = sTI,
                                study_settings = self.study_settings,
                                folder_path = folder_path,
                                parallel_env='openmp_fast'))

        #Run the tasks
        test=SGE_test()
        test.set_deps(self.tasks)

        print(print_tree(test))
        #exit(1)

        #run SGE_test on login node to bypass scheduler
        n_workers=len(self.hosts)*len(self.ligands)*len(self.states)*\
                    self.n_repeats*self.n_sampling_sims
        luigi.build([test],
                    worker_scheduler_factory=my_WorkerSchedulerFactory(),
                    local_scheduler=True, workers=n_workers)
        #luigi.build([test], workers=2)



# ==============================================================================
#                               MAIN
# ==============================================================================

def main(args):
    """Run the main script.

    Parameters
    ----------
    args : argparse.Namespace
        The command line arguments
    """
    toppath=os.path.abspath(args.toppath)
    mdppath=os.path.abspath(args.mdppath)
    basepath=os.path.abspath(args.basepath)

    w=SGE_Workflow_aligned_in_Protein(toppath, mdppath, ["BRD1"], ["lig"],
                         basepath=basepath,
                         #b=args.b,
                         b=0,
                         #mdrun="mdrun_threads_AVX2_256",
                         mdrun="gmx mdrun",
                         #mdrun_opts="-pin on -nsteps 1000"
                         mdrun_opts="-pin on"
                         )

    w.run_everything()

    print("Complete.\n")

if __name__ == '__main__':
    args = parse_options()
    main(args)
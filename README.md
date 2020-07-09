
<h1>OpenMATB: An open-source version of the Multi-Attribute Task Battery (MATB)</h1>

<b><a href="https://github.com/juliencegarra/OpenMATB/releases/download/1.1/OpenMATB_v1.1.000.zip">Click here to download the last binary for Windows (v1.1)</a></b>

First presented at a NASA Technical memorandum (Comstock & Arnegard, 1992), the Multi-Attribute Task Battery (MATB) contained a set of interactive tasks that were representative of those performed in aircraft piloting. The MATB requires participants to engage in four tasks presented simultaneously on a computer screen. They consist of (1) a monitoring task, (2) a tracking task, (3) an auditory communication task, and (4) a resource management task. The display screen also encompasses a scheduling view (5) for displaying a chart of incoming task events

<center><img src="https://user-images.githubusercontent.com/10955668/49248376-d6ce3c80-f419-11e8-9416-7e0fe3e11d45.png" width=400></center>

Almost twenty years have passed since the last iteration of the MATB implementation (Comstock & Arnegard, 1992), different requirements for up to date research are no longer satisfied. 
OpenMATB aims to provide an open-source re-implementation of the multi-attribute task battery. It promotes three aspects: 
(1) tasks customization for full adaptation of the battery,
(2) software extendability to easily add new features, 
(3) experiment replicability to provide significant results.

Those aspects are detailed in: Cegarra, J., Valéry, B., Avril, E., Calmettes, C. & Navarro, J. (2020). OpenMATB: An open source implementation of the Multi-Attribute Task Battery. <i>Behavior Research Methods</i> https://doi.org/10.3758/s13428-020-01364-w


Contact : <a href="mailto:julien.cegarra@univ-jfc.fr">julien.cegarra AT univ-jfc.fr</a>


<h2>Installation</h2>

The program requires Python 3.x (tested on version 3.8) and the corresponding version of the Pygame, PySide2 and rstr libraries, freely available online. Make sure you install the matching (32- or 64-bit) version of Pygame as your Python installation, and the one compatible with your Python version number.

The program was tested under Windows and Linux systems. Some minimal code updates are expected to run under mac.

To run perfectly, the software requires only a personal computer and a joystick for the tracking task. 

It is covered by a GPL v3 license to promote exchange between researchers, granting them the permission not only to run and to study the source code, but also to share their software modifications.


<h3>Main complementary resources:</h3>
<ul>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Main-differences-between-the-published-implementations-of-the-MATB-and-the-OpenMATB">Main differences between the existing published implementations of the MATB and the OpenMATB</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Sample-script:-Replication-of-Parasuraman,-Molloy-and-Singh-(1993)">Sample script: Replication of Parasuraman, Molloy and Singh (1993)</a></li>  
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/How-to-build-a-scenario-file">How to develop a scenario script file</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/List-of-task-parameters">List of available parameters in the scenario files</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Internationalization">How to add a new translation</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Write-a-questionnaire">How to add custom rating scales</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Present-instructions">How to interpose instructions during the experiment?</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/How-to-compile-to-binary">How to compile the source code to a binary version (Windows)</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Technical-documentation">Misc technical aspects (in progress)</a></li>

</ul>










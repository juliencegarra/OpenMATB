
<h1>OpenMATB: An open-source version of the Multi-Attribute Task Battery (MATB)</h1>

<b><a href="">Click here to download the last binary for Windows (v1.0)</a></b>

First presented at a NASA Technical memorandum (Comstock & Arnegard, 1992), the Multi-Attribute Task Battery (MATB) contained a set of interactive tasks that were representative of those performed in aircraft piloting. The MATB requires participants to engage in four tasks presented simultaneously on a computer screen. They consist of (1) a monitoring task, (2) a tracking task, (3) an auditory communication task, and (4) a resource management task. The display screen also encompasses a scheduling view (5) for displaying a chart of incoming task events

<center><img src="https://raw.githubusercontent.com/juliencegarra/OpenMATB/master/OpenMATBscreenshot.png" width=400></center>

Since almost twenty years have passed since the last iteration of the MATB implementation (Comstock & Arnegard, 1992), different requirements for up to date research are no longer satisfied. More precisely, OpenMATB promote three aspects: 
(1) tasks customization for full adaptation of the battery,
(2) software extendability to easily add new features, 
(3) experiment replicability to provide significant results.

Those aspects are detailed in: Cegarra, J., Valéry, B., Avril, E., Calmettes, C. & Navarro, J. (<i>Submitted</i>). OpenMATB: An open source implementation of the Multi-Attribute Task Battery.



<h2>Installation</h2>

The program requires Python 2.x (tested on version 2.7) and the corresponding version of the Pygame, PySide and rstr libraries, freely available online. Make sure you install the matching (32- or 64-bit) version of Pygame as your Python installation, and the one compatible with your Python version number.

The program was tested under Windows and Linux systems. Some minimal code updates are expected to run under mac.

To run perfectly, the software requires only a personal computer and a joystick for the tracking task. 

It is covered by a GPL v3 license to promote exchange between researchers, granting them the permission not only to run and to study the source code, but also to share their software modifications.


<h3>Complementary resources</h3>
<ul>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/How-to-build-a-scenario-file">Wiki page on the way to develop scenario with OpenMATB</a></li>
<li><a href="Appendix.doc">More detailed about customization of the tasks is available in the appendix</a></li>
<li><a href="https://github.com/juliencegarra/OpenMATB/wiki/Internationalization">Wiki page about internationalization of the software</a></li>
</ul>










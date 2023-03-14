# Copyright 2023, by Julien Cegarra & Benoît Valéry. All rights reserved.
# Institut National Universitaire Champollion (Albi, France).
# License : CeCILL, version 2.1 (see the LICENSE file)

from plugins import Instructions

try:
    from core import pylsl
except:
    print("unable to import pylsl")

class Labstreaminglayer(Instructions):
    def __init__(self, window):
        super().__init__(window)

        self.parameters.update({'marker':'', 'streamsession':False,
                                'pauseatstart':False})

        self.stream_info = None
        self.stream_outlet = None
        self.stop_on_end = False

        self.lsl_wait_msg = _("Please enable the OpenMATB stream into your LabRecorder.")        
        

    def start(self):
        # If we get there it's because the plugin is used.
        # If pylsl is not available this part should fail.
        # Create a LSL marker outlet.            
        super().start()
        self.stream_info = pylsl.StreamInfo('OpenMATB', type='Markers', channel_count=1,
                                             nominal_srate=0, channel_format='string',
                                             source_id='myuidw435368')
        self.stream_outlet = pylsl.StreamOutlet(self.stream_info)

        if self.parameters['pauseatstart'] is True:
            self.slides = [self.get_msg_slide_content(self.lsl_wait_msg)]
            

    def update(self, dt):
        super().update(dt)

        if self.parameters['streamsession'] is True and self.logger.lsl is None:
            self.logger.lsl = self
        elif self.parameters['streamsession'] is False and self.logger.lsl is not None:
            self.logger.lsl = None
        
        if self.parameters['marker'] != '':
            # A marker has been set. Push it to the outlet.
            self.push(self.parameters['marker'])

            # and reset the marker to empty.
            self.parameters['marker'] = ''

    
    def push(self, message):
        if self.stream_outlet is None:
            return
        self.stream_outlet.push_sample([message])
#        print(message)



    def stop(self):
        super().stop()
        self.stream_info = None
        self.stream_outlet = None
        
        
    def get_msg_slide_content(self, str_msg):
        return f"<title>Lab streaming layer\n{self.lsl_wait_msg}"


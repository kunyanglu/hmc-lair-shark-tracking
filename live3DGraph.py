import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.widgets import CheckButtons
import constants as const

"""
Uses matplotlib to generate live 3D Graph while the simulator is running

Able to draw the auv as well as multiple sharks
"""
class Live3DGraph:
    def __init__(self):
        self.shark_array = []

        # array of pre-defined colors, 
        # so we can draw sharks with different colors
        self.colors = ['b', 'g', 'c', 'm', 'y', 'k']

        # initialize the 3d scatter position plot for the auv and shark
        self.fig = plt.figure(figsize = [13, 10])
        self.ax = self.fig.add_subplot(111, projection='3d')

        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')

        self.arrow_length_ratio = 0.1

        # create a dictionary for checkbox for each type of planned trajectory
        # key - the planner's name: "A *", "RRT"
        # value - three-element array
        #   1. boolean(represent wheter the label is added to the legend)
        #   2. the CheckButtons object
        #   3. color of the plot
        self.traj_checkbox_dict = {}
        
        # initialize the A * button
        self.traj_checkbox_dict["A *"] = [False,\
            CheckButtons(plt.axes([0.7, 0.10, 0.15, 0.05]), ["A* Trajectory"]), '#9933ff']
        # when the A* checkbox is checked, it should call self.enable_traj_plot
        
        # initialize the RRT button
        self.traj_checkbox_dict["RRT"] = [False,\
            CheckButtons(plt.axes([0.7, 0.05, 0.15, 0.05]),["RRT Trajectory"]), '#043d10']
        # when the RRT checkbox is checked, it should call self.enable_traj_plot

        self.particle_checkbox = CheckButtons(plt.axes([0.1, 0.10, 0.15, 0.05]),["Display Particles"])
        self.display_particles = False
        self.particle_checkbox.on_clicked(self.particle_checkbox_clicked)
        # an array of the labels that will appear in the legend
        # TODO: labels and legends still have minor bugs
        self.labels = ["auv"]


    def scale_quiver_arrow(self):
        """
        A hack to work around the bug with quiver plot arrow size

        Manually alter the arrow_length_ratio which affects the arrow size partially
        """
        # The current theory is that the arrow size is weird because the z axis is being autoscaled
        # A work-around is to adjust the arrow size based on the z axis range
        z_interval = self.ax.get_zaxis().get_data_interval()
        range = abs(z_interval[0] - z_interval[1])

        if range == 0:
            # if the distance between the auv and sharks is 0 m in the z direction
            self.arrow_length_ratio = 0.01
        elif range > 50:
            # if the distance between the auv and sharks is greater than 50 m in the z direction
            self.arrow_length_ratio = range * 0.02
        else:
            self.arrow_length_ratio = range * 0.1


    def plot_auv(self, x_pos_array, y_pos_array, z_pos_array):
        """
        Plot the auv trajectory as well as its direction

        Parameters:
            x_pos_array - an array of floats indicating the auv's past x-position
            y_pos_array - an array of floats indicating the auv's past y-position
            z_pos_array - an array of floats indicating the auv's past z-position
        """
        # plot the trajectory line
        self.ax.plot(x_pos_array, y_pos_array, z_pos_array,\
            marker = ',', linestyle = '-', color = 'red', label='auv')

        # calculate the orientation of 
        x_orient = x_pos_array[-1]-x_pos_array[-2]
        y_orient = y_pos_array[-1]-y_pos_array[-2]
        z_orient = z_pos_array[-1]-z_pos_array[-2]

        # use quiver plot to draw an arrow indicating the auv's direction
        self.ax.quiver(x_pos_array[-1], y_pos_array[-1], z_pos_array[-1],\
            x_orient, y_orient, z_orient,\
            color = 'red', pivot="tip", normalize=True, arrow_length_ratio = self.arrow_length_ratio)


    def load_shark_labels(self):
        """
        Add the sharks that we are tracking to the legend
        
        Should be called in setup() in robotSim after the shark tracking data is loaded
        """
        if len(self.shark_array) != 0:
             # create legend with the auv and all the sharks
            self.labels += list(map(lambda s: "shark #" + str(s.id), self.shark_array))
    

    def plot_sharks(self, sim_time):
        """
        Plot the trajectory of all the sharks that the robot is 
        tracking in this simulation
        """
        # check if there is any shark to draw
        # and if we have already looped through all the trajectory points
        if len(self.shark_array) != 0:         
            for i in range(len(self.shark_array)):
                if self.shark_array[0].index < len(self.shark_array[0].traj_pts_array):
                    # determine the color of this shark's trajectory
                    c = self.colors[i % len(self.colors)]
                    shark = self.shark_array[i]
                    
                    # increment index variable so we get new position from the shark
                    # The shark trajectories have time interval of 0.03s between each trajectory,
                    #   but the simulator time interval might be diffent.
                    # So we need to increment the index properly so that the newest shark trajectory point is close
                    #   to the simulator's current time
                    while shark.index < len(shark.traj_pts_array) and\
                        abs(shark.traj_pts_array[shark.index].time_stamp - sim_time) > (const.SIM_TIME_INTERVAL + 0.1):
                        shark.index += 1

                    # update the shark's position arrays to help us update the graph
                    shark.store_positions(shark.traj_pts_array[shark.index].x, shark.traj_pts_array[shark.index].y, shark.traj_pts_array[shark.index].z)

                    # calculate orientation by: current coordinate - previous coordinate
                    # these 3 variables will help us indicate the direction of the trajectory
                    x_orient = shark.x_pos_array[-1]-shark.x_pos_array[-2]
                    y_orient = shark.y_pos_array[-1]-shark.y_pos_array[-2]
                    z_orient = shark.z_pos_array[-1]-shark.z_pos_array[-2]
                    
                    # plot the trajectory of the shark
                    self.ax.plot(shark.x_pos_array, shark.y_pos_array, shark.z_pos_array, marker = ",", color = c, label = "shark #" + str(shark.id))

                    # plot the direction vectors for the shark
                    self.ax.quiver3D(shark.x_pos_array[-1], shark.y_pos_array[-1], shark.z_pos_array[-1], x_orient, y_orient, z_orient, color = c, pivot="tip", normalize = True, arrow_length_ratio = self.arrow_length_ratio)

            
    def enable_traj_plot(self, event):
        """
        Handles when a check box is hit

        event - a string, matches with the name of the label when the checkButton is created
        """
        if (event == "A* Trajectory"):
            # self.traj_checkbox_dict["A *"][0] returns whether the label has been added to 
            #   self.labels aka the legend
            # we only want one copy of the label to be in self.labels
            if not self.traj_checkbox_dict["A *"][0]:
                self.labels += ["A *"]
                self.traj_checkbox_dict["A *"][0] = True
        elif (event == "RRT Trajectory"):
            if not self.traj_checkbox_dict["RRT"][0]:
                self.labels += ["RRT"]
                self.traj_checkbox_dict["RRT"][0] = True        


    def plot_planned_traj(self, planner_name, trajectory_array):
        """
        Plot the planned trajectory specified by the planner name

        Parameters:
            planner_name - string, either "A *" or "RRT"
            trajectory_array - an array of Motion_plan_state objects
        """
        # get the checkbox object
        checkbox = self.traj_checkbox_dict[planner_name][1]
        # boolean, true if the checkbox is checked
        checked = checkbox.get_status()[0]
        # get the color of the trajectory plot (a string representing color in hex)
        color = self.traj_checkbox_dict[planner_name][2]
        
        if checked:
            # self.traj_checkbox_dict["A *"][0] returns whether the label has been added to 
            #   self.labels aka the legend
            # we only want one copy of the label to be in self.labels 
            if not self.traj_checkbox_dict[planner_name][0]:
                self.labels += [planner_name]
                self.traj_checkbox_dict[planner_name][0] = True
            
            traj_x_array = []
            traj_y_array = []
            # create two array of x and y positions for plotting
            for traj_pt in trajectory_array:
                traj_x_array.append(traj_pt.x)
                traj_y_array.append(traj_pt.y)

            # TODO: for now, we set the z position of the trajectory to be -10
            self.ax.plot(traj_x_array,  traj_y_array, 0, marker = ',', color = color, label = planner_name)
        else:
            # if the checkbox if not checked
            # self.traj_checkbox_dict[planner_name][0] represents whether the label is added to
            #   self.label array
            # we only want to remove the label once
            if self.traj_checkbox_dict[planner_name][0]:
                self.labels.remove(planner_name)
                self.traj_checkbox_dict[planner_name][0] = False
    

    def particle_checkbox_clicked(self, event):
        """
        on_clicked handler function for particle checkbox

        toggle the display_particles variable (bool)
        """
        self.display_particles = not self.display_particles
    
    
    def plot_particles(self, particle_array):
        """
        Plot the particles if the the particle checkbox is checked

        Parameter:
            particle_array - an array of arrays, where each element has the format:
                [x_p, y_p, v_p, theta_p, weight_p]
        """
        if self.display_particles:
            particle_x_array = []
            particle_y_array = []
            # create two arrays for plotting x and y positions
            for particle in particle_array:
                particle_x_array.append(particle[0])
                particle_y_array.append(particle[1])
            
            # TODO: for now, we set the z position of the trajectory to be -10
            self.ax.scatter(particle_x_array, particle_y_array, -10, marker = 'o', color = '#069ecc')
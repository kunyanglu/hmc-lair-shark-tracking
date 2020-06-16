# add all the stuff we gotta import
import math
import decimal
import time
import numpy as np
import random
from copy import copy, deepcopy
from numpy import random
import matplotlib.pyplot as plt
from numpy.random import uniform 
from numpy.random import randn
import threading
#from particle import Particle
from robotSim import RobotSim
from live3DGraph import Live3DGraph
from twoDfigure import Figure
from motion_plan_state import Motion_plan_state

def angle_wrap(ang):
    """
    Takes an angle in radians & sets it between the range of -pi to pi

    Parameter:
        ang - floating point number, angle in radians

    USE ANY TIME THERE IS AN ANGLE CALCULATION
    """
    if -math.pi <= ang <= math.pi:
        return ang
    elif ang > math.pi: 
        ang += (-2 * math.pi)
        return angle_wrap(ang)
    elif ang < -math.pi: 
        ang += (2 * math.pi)
        return angle_wrap(ang)

def velocity_wrap(velocity):
    if velocity <= 5:
        return velocity  
    elif velocity > 5: 
        velocity += -5
        return velocity_wrap(velocity)

class Particle: 
        def __init__(self, x_shark, y_shark):
            #set L (side length of square that the random particles are in) and N (number of particles)
            INITIAL_PARTICLE_RANGE = 150
            NUMBER_OF_PARTICLES = 900
            #particle has 5 properties: x, y, velocity, theta, weight (starts at 1/N)
            self.x_p = x_shark + random.uniform(-INITIAL_PARTICLE_RANGE, INITIAL_PARTICLE_RANGE)
            self.y_p = y_shark + random.uniform(-INITIAL_PARTICLE_RANGE, INITIAL_PARTICLE_RANGE)
            self.v_p = random.uniform(0, 5)
            self.theta_p = random.uniform(-math.pi, math.pi)
            self.weight_p = 1/NUMBER_OF_PARTICLES

        def update_particle(self, dt):
            """
                updates the particles location with random v and theta

                input (dt) is the amount of time the particles are "moving" 
                    generally set to .1, but it should be whatever the "time.sleep" is set to in the main loop

            """

            #random_v and random_theta are values to be added to the velocity and theta for randomization
            RANDOM_VELOCITY = 5
            RANDOM_THETA = math.pi/2
            #change velocity & pass through velocity_wrap
            self.v_p += random.uniform(0, RANDOM_VELOCITY)
            self.v_p = velocity_wrap(self.v_p)
            #change theta & pass through angle_wrap
            self.theta_p += random.uniform(-RANDOM_THETA, RANDOM_THETA)
            self.theta_p = angle_wrap(self.theta_p)
            #change x & y coordinates to match 
            self.x_p += self.v_p * math.cos(self.theta_p) * dt
            self.y_p += self.v_p * math.sin(self.theta_p) * dt
            
            
        def calc_particle_alpha(self, x_auv, y_auv, theta_auv):
            """
                calculates the alpha value of a particle
            """
            particleAlpha = angle_wrap(math.atan2((-y_auv + self.y_p), (self.x_p + -x_auv))) - theta_auv
            return particleAlpha

        def calc_particle_range(self, x_auv, y_auv):
            """
                calculates the range from the particle to the auv
            """
            particleRange = math.sqrt((y_auv - self.y_p)**2 + (x_auv - self.x_p)**2)
            return particleRange

        def weight(self, auv_alpha, particleAlpha, auv_range, particleRange):
            """
                calculates the weight according to alpha, then the weight according to range
                they are multiplied together to get the final weight
            """
            
            #alpha weight
            SIGMA_ALPHA = .5
            
            if particleAlpha > 0:
                function_alpha = .001 + (1/(SIGMA_ALPHA * math.sqrt(2*math.pi))* (math.e**(((-((angle_wrap(float(particleAlpha) - auv_alpha[0])**2))))/(2*(SIGMA_ALPHA)**2))))
                self.weight_p = function_alpha
            elif particleAlpha == 0:
                function_alpha = .001 + (1/(SIGMA_ALPHA * math.sqrt(2*math.pi))* (math.e**(((-((angle_wrap(float(particleAlpha) - auv_alpha[0])**2))))/(2*(SIGMA_ALPHA)**2))))
                self.weight_p = function_alpha
            else:
                function_alpha = .001 + (1/(SIGMA_ALPHA * math.sqrt(2*math.pi))* (math.e**(((-((angle_wrap(float(particleAlpha) - auv_alpha[0])**2))))/(2*(SIGMA_ALPHA)**2))))
                self.weight_p = function_alpha
    
            #range weight
            SIGMA_RANGE = 10
            function_weight =  .001 + (1/(SIGMA_RANGE * math.sqrt(2*math.pi))* (math.e**(((-((particleRange - auv_range)**2)))/(2*(SIGMA_RANGE)**2))))
            
            #multiply weights
            self.weight_p = function_weight * self.weight_p

class particleFilter:
    # 2 sets of initial data- shark's initial position and velocity, and position of AUV 
    # output- estimates the sharks position and velocity
    def __init__(self, init_x_shark, init_y_shark, init_theta, init_x_auv, init_y_auv):
        "how you create an object out of the particle Filter class i.e. "
        self.x_shark = init_x_shark
        self.y_shark = init_y_shark
        self.theta = init_theta
        self.x_auv = init_x_auv
        self.y_auv = init_y_auv

    def updateShark(self, dt):
        v_x_shark = random.uniform(-5, 5)
        v_y_shark = random.uniform(-5, 5)
        self.x_shark = self.x_shark + (v_x_shark * dt)
        self.y_shark = self.y_shark + (v_y_shark * dt)
        return [self.x_shark, self.y_shark]

    def auv_to_alpha(self):
        #calculates auv's alpha from the shark
        list_of_real_alpha = []
        real_alpha = angle_wrap(math.atan2((-self.y_auv + self.y_shark), (self.x_shark- self.x_auv))) - self.theta
        list_of_real_alpha.append(real_alpha)
        list_of_real_alpha.append(-real_alpha)
        #print("list of alpha")
        #print(list_of_real_alpha)
        return list_of_real_alpha

    def range_auv(self):
        range = []
        range_value = math.sqrt((float(self.y_auv)- self.y_shark)**2 + (float(self.x_auv)-float(self.x_shark))**2)
        range.append(range_value)
        #print("range of auv is")
        #print(range)
        return range_value
   
    def normalize(self, weights_list):
        newlist = []
        denominator= max(weights_list)
        for weight in weights_list:
            weight1 = (1/ denominator) * weight
            newlist.append(weight1)
        #print("new weight hopefully")
        #print(newlist)
        return newlist

    def particleMean(self, new_particles):
        """caculates the mean of the particles x and y positions"""
        sum_x = 0
        sum_y = 0
        x_mean = 0
        y_mean = 0
        count = 0
        for particle in new_particles:
            sum_x += particle.x_p
            sum_y += particle.y_p
            count += 1
        x_mean = sum_x/count
        y_mean = sum_y/ count
        xy_mean = [x_mean, y_mean]
        return xy_mean

    def meanError(self, x_mean, y_mean):
        
        x_difference = x_mean - self.x_shark
        y_difference = y_mean - self.y_shark
        range_error = math.sqrt((x_difference**2) + (y_difference **2))
        #alpha_error = math.atan2(y_difference, x_difference)
        #print("error")
        #print(range_error)
        return (range_error)

    def correct(self, normalize_list, old_coordinates):
        list_of_new_particles = []
        new_particles = []
        copy = []
        count = -1
        #print(normalize_list)
        for particle in old_coordinates:
            if particle.weight_p < 0.2:
                count += 1
                #print(particle.weight_p)
                copy = deepcopy(particle)
                list_of_new_particles.append(copy)
                    
                    #list_of_new_particles.append(copy)
                    #print("count, ", count, "x, y", old_coordinates[count][:2] )
                    #print(list_of_new_particles)
            elif particle.weight_p < 0.4:
                #print(particle.weight_p)
                count += 1
                copy1 = deepcopy(particle)
                list_of_new_particles.append(copy1)
                copy2 = deepcopy(particle)
                list_of_new_particles.append(copy2)
                    
                    #print(list_of_new_particles)
            elif particle.weight_p < 0.6:
                #print(particle.weight_p)
                count += 1
                copy3 = deepcopy(particle)
                list_of_new_particles.append(copy3)
                copy4 = deepcopy(particle)
                list_of_new_particles.append(copy4)                    
                copy5 = deepcopy(particle)
                list_of_new_particles.append(copy5)
                    

                    #print(list_of_new_particles)
            elif particle.weight_p < .8:
                #print(particle.weight_p)
                count += 1
                copy6 = deepcopy(particle)
                list_of_new_particles.append(copy6)
                copy7 = deepcopy(particle)
                list_of_new_particles.append(copy7)
                copy8 = deepcopy(particle)
                list_of_new_particles.append(copy8)
                copy9 = deepcopy(particle)
                list_of_new_particles.append(copy9)
                    
                    
                    #print(list_of_new_particles)
            elif particle.weight_p <= 1.0:
                #print(particle.weight_p)
                count += 1
                copy10 = deepcopy(particle)
                list_of_new_particles.append(copy10)
                copy11 = deepcopy(particle)
                list_of_new_particles.append(copy11)
                copy12 = deepcopy(particle)
                list_of_new_particles.append(copy12)
                copy13 = deepcopy(particle)
                list_of_new_particles.append(copy13)
                copy14 = deepcopy(particle)
                list_of_new_particles.append(copy14)
            else:
                print("something is not right with the weights")
        #print('list of new particles')
        #print(list_of_new_particles)
        
        #for particle in list_of_new_particles: 
           # print("x:", particle.x_p, " y:", particle.y_p, " velocity:", particle.v_p, " theta:", particle.theta_p, " weight:", particle.weight_p)
        #print(count)
        for n in range(len(normalize_list)): 
            x = random.choice(len(list_of_new_particles))
            new_particles.append(list_of_new_particles[x])
        #print("new particles")
        #print(new_particles)
        return new_particles
    
    def particle_coordinates(self, particles): 
        particle_coordinates = []
        individual_coordinates = []
        for particle in particles:
            individual_coordinates.append(particle.x_p)
            individual_coordinates.append(particle.y_p)
            individual_coordinates.append(particle.weight_p)
            #print("individual coordinates", individual_coordinates)
            particle_coordinates.append(individual_coordinates)
            individual_coordinates = []
            #print("particle_coordinates", particle_coordinates)
        return particle_coordinates
    
    """
    def cluster_over_time_function(self, particles, actual_shark_coordinate_x, actual_shark_coordinate_y, sim_time, list_of_error_mean):
        list_of_answers = []
        count = 0
        for particle in particles:
            sum = abs(particle.x_p - final_new_shark_coordinate_x[-1]) + abs(particle.y_p - final_new_shark_coordinate_x[-1])
            if sum <= 1.1* (list_of_error_mean[index_number_of_particles])
                count += 1
                if count >= NUMBER_OF_PARTICLES *0.8
                    list_of_answers.append(sim_time)
        return list_of_answers
    """


    
            
def main(): 
    NUMBER_OF_PARTICLES = 900
    #change this constant ^^ in the particle class too!
    particles = []
    
    #test_grapher = Live3DGraph()
    test_grapher_shark = Figure()
    #shark's initial x, y, z, theta
    test_shark = RobotSim(740, 280, -5, 0.1)
    test_shark.setup("./data/sharkTrackingData.csv", [1])

    x_auv = 740
    y_auv = 230
    theta = 0 
    # for now, since the auv is stationary, we can just set it like this
    auv_pos = Motion_plan_state(x_auv, y_auv, theta)
    # example of how to get the shark x position and y position
    shark_list = test_shark.live_graph.shark_array
    shark = test_shark.live_graph.shark_array[0]
    print("shark pos initial")
    print(shark.x_pos_array)
    print(shark.y_pos_array)
    initial_x_shark = shark.x_pos_array[0]
    initial_y_shark = shark.y_pos_array[0]
    test_particle = particleFilter(initial_x_shark, initial_y_shark, theta, x_auv ,y_auv)
    final_new_shark_coordinate_x = []
    final_new_shark_coordinate_y = []
    actual_shark_coordinate_x = []
    actual_shark_coordinate_y = []
    final_new_shark_coordinate_x.append(initial_x_shark)
    final_new_shark_coordinate_y.append(initial_y_shark)
    actual_shark_coordinate_x.append(initial_x_shark)
    actual_shark_coordinate_y.append(initial_y_shark)

    for x in range(0, NUMBER_OF_PARTICLES):
        new_particle = Particle(initial_x_shark, initial_y_shark)
        particles.append(new_particle)

    #print("original particles (random)")
    #for particle in particles:
    #    print("x:", particle.x_p, " y:", particle.y_p, " velocity:", particle.v_p, " theta:", particle.theta_p, " weight:", particle.weight_p)

    #print("updated particles after", .1, "seconds of random movement")
    for particle in particles: 
        particle.update_particle(.1)
        #print("x:", particle.x_p, " y:", particle.y_p, " velocity:", particle.v_p, " theta:", particle.theta_p, " weight:", particle.weight_p)

    shark_state_dict = test_shark.get_all_sharks_state()
    has_new_data = test_shark.get_all_sharks_sensor_measurements(shark_state_dict, auv_pos)
    test_shark.shark_sensor_data_dict[1]
    test_particle.x_shark = test_shark.shark_sensor_data_dict[1].x
    test_particle.y_shark = test_shark.shark_sensor_data_dict[1].y
    auv_alpha = test_particle.auv_to_alpha()
    auv_range = test_particle.range_auv()

    #print("auv range and alpha", auv_alpha, auv_range)

    for particle in particles: 
        particleAlpha = particle.calc_particle_alpha(x_auv, y_auv, theta)
        particleRange = particle.calc_particle_range(x_auv, y_auv)
        particle.weight(auv_alpha, particleAlpha, auv_range, particleRange)
        #print("weight: ", particle.weight_p)

    list_of_weights = []
    for particle in particles: 
        list_of_weights.append(particle.weight_p)

    normalized_weights = test_particle.normalize(list_of_weights)
    count = 0
    for particle in particles: 
        particle.weight_p = normalized_weights[count]
        #print("new normalized particle weight: ", particle.weight_p)
        count += 1


    xy_mean = test_particle.particleMean(particles)
    x_mean_over_time = []
    y_mean_over_time = []
    x_mean_over_time.append(xy_mean[0])
    y_mean_over_time.append(xy_mean[1])
    #print(x_mean_over_time)
    # print("error (x, y): ", xy_mean)

    tracking_error_list = []
    tracking_error_list.append(test_particle.meanError(xy_mean[0], xy_mean[1]))

    new_particles = test_particle.correct(normalized_weights, particles)
    particles = new_particles
    #for particle in particles: 
        #print("x:", particle.x_p, " y:", particle.y_p, " velocity:", particle.v_p, " theta:", particle.theta_p, " weight:", particle.weight_p)
    particle_coordinates = test_particle.particle_coordinates(particles)

    loops = 0
    sim_time = 0.0
    index_number_of_particles = 0

    while True: 
        
        loops += 1
        print(loops)
        time.sleep(.1)
            #print("x:", particle.x_p, " y:", particle.y_p, " velocity:", particle.v_p, " theta:", particle.theta_p, " weight:", particle.weight_p)
        #print("updated particles after", .1, "seconds of random movement")
        # update the shark position (do this in your main loop)
        for particle in particles: 
            particle.update_particle(.1)

        for shark in shark_list:
            test_shark.live_graph.update_shark_location(shark, sim_time)
        
        shark_state_dict = test_shark.get_all_sharks_state()

        #print("==================")
        #print("All the Shark States [x, y, ..., time_stamp]: " + str(shark_state_dict))

        has_new_data = test_shark.get_all_sharks_sensor_measurements(shark_state_dict, auv_pos)


        if has_new_data == True:
            print("======NEW DATA=======")
            print("All The Shark Sensor Measurements [range, bearing]: " +\
                str(test_shark.shark_sensor_data_dict))
        
        test_particle.x_shark = test_shark.shark_sensor_data_dict[1].x
        test_particle.y_shark = test_shark.shark_sensor_data_dict[1].y
        auv_alpha = test_particle.auv_to_alpha()
        auv_range = test_particle.range_auv()
        
        #print(" range in the loop")
        #print(auv_alpha, auv_range)

        for particle in particles: 
            particleAlpha = particle.calc_particle_alpha(x_auv, y_auv, theta)
            particleRange = particle.calc_particle_range(x_auv, y_auv)
            particle.weight(auv_alpha, particleAlpha, auv_range, particleRange)
            #print("weight: ", particle.weight_p)

        list_of_weights = []
        for particle in particles: 
            list_of_weights.append(particle.weight_p)

        normalized_weights = test_particle.normalize(list_of_weights)
        count = 0
        for particle in particles: 
            particle.weight_p = normalized_weights[count]
            #print("particle weight: ", particle.weight_p)
            count += 1
        
        new_particles = test_particle.correct(normalized_weights, particles)
        particles = new_particles

        sim_time += 0.1

        xy_mean = test_particle.particleMean(particles)
        print("mean of all particles (x, y): ", xy_mean)
        x_mean_over_time.append(xy_mean[0])
        y_mean_over_time.append(xy_mean[1])
        tracking_error_list.append(test_particle.meanError(xy_mean[0], xy_mean[1]))

        final_new_shark_coordinate_x.append(test_particle.x_shark)
        final_new_shark_coordinate_y.append(test_particle.y_shark)
        actual_shark_coordinate_x.append(shark.x_pos_array[-1])
        actual_shark_coordinate_y.append(shark.y_pos_array[-1])

        particle_coordinates = test_particle.particle_coordinates(particles)
        print("+++++++++++++++++++++++++++++++")
        #print(particle_coordinates)
        
        #simulation stuff

        print("===================")
        print(final_new_shark_coordinate_x)
        print("=====================================")
        #print(particle_coordinates)
        """
        test_shark.live_graph.plot_particles(particle_coordinates, final_new_shark_coordinate_x, final_new_shark_coordinate_y, actual_shark_coordinate_x, actual_shark_coordinate_y)
        plt.draw()
        plt.pause(.1)
        test_shark.live_graph.ax.clear()
        """
    plt.close()
    test_grapher_shark.coordinate_plotter(x_mean_over_time, y_mean_over_time, final_new_shark_coordinate_x, final_new_shark_coordinate_y)
    plt.show()

        

if __name__ == "__main__":
    main()
import gym
import math
import random
import time
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from collections import namedtuple
from itertools import count
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision.transforms as T  

from motion_plan_state import Motion_plan_state

# namedtuple allows us to store Experiences as labeled tuples
Experience = namedtuple('Experience', ('state', 'action', 'next_state', 'reward'))

"""
============================================================================

    Parameters

============================================================================
"""

# define the range between the starting point of the auv and shark
dist = 10.0
MIN_X = dist
MAX_X= dist * 2
MIN_Y = 0.0
MAX_Y = dist * 3

NUM_OF_EPISODES = 5
MAX_STEP = 1000

N_V = 7
N_W = 7

GAMMA = 0.999

EPS_START = 1
EPS_END = 0.05
EPS_DECAY = 0.001

LEARNING_RATE = 0.001

MEMORY_SIZE = 100000
BATCH_SIZE = 64

# number of additional goals to be added to the replay memory
NUM_GOALS_SAMPLED_HER = 4

TARGET_UPDATE = 10

NUM_OF_OBSTACLES = 0
STATE_SIZE = 8 + NUM_OF_OBSTACLES * 4

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# how many episode should we save the model
SAVE_EVERY = 10
# how many episode should we render the model
RENDER_EVERY = 1

DEBUG = True

"""
============================================================================

    Helper Functions

============================================================================
"""
def process_state_for_nn(state):
    """
    Convert the state (observation in the environment) to a tensor so it can be passed into the neural network

    Parameter:
        state - a tuple of two np arrays
            Each array is this form [x, y, z, theta]
    """
    auv_tensor = torch.from_numpy(state[0])
    shark_tensor = torch.from_numpy(state[1])
    obstacle_tensor = torch.from_numpy(state[2])
    obstacle_tensor = torch.flatten(obstacle_tensor)
    
    # join 2 tensor together
    return torch.cat((auv_tensor, shark_tensor, obstacle_tensor)).float()


def extract_tensors(experiences):
    """
    Convert batches of experiences sampled from the replay memeory to tuples of tensors
    """
    batch = Experience(*zip(*experiences))
   
    t1 = torch.stack(batch.state)
    t2 = torch.stack(batch.action)
    t3 = torch.cat(batch.reward)
    t4 = torch.stack(batch.next_state)

    return (t1,t2,t3,t4)


def save_model(policy_net, target_net):
    print("Model Save...")
    torch.save(policy_net.state_dict(), 'checkpoint_policy.pth')
    torch.save(target_net.state_dict(), 'checkpoint_target.pth')


def calculate_range(a_pos, b_pos):
        """
        Calculate the range (distance) between point a and b, specified by their coordinates

        Parameters:
            a_pos - an array / a numpy array
            b_pos - an array / a numpy array
                both have the format: [x_pos, y_pos, z_pos, theta]

        TODO: include z pos in future range calculation?
        """
        a_x = a_pos[0]
        a_y = a_pos[1]
        b_x = b_pos[0]
        b_y = b_pos[1]

        delta_x = b_x - a_x
        delta_y = b_y - a_y

        return np.sqrt(delta_x**2 + delta_y**2)


def validate_new_obstacle(new_obstacle, new_obs_size, auv_init_pos, shark_init_pos, obstacle_array):
    """
    Helper function for checking whether the newly obstacle generated is valid or not
    """
    auv_overlaps = calculate_range([auv_init_pos.x, auv_init_pos.y], new_obstacle) <= new_obs_size
    shark_overlaps = calculate_range([shark_init_pos.x, shark_init_pos.y], new_obstacle) <= new_obs_size
    obs_overlaps = False
    for obs in obstacle_array:
        if calculate_range([obs.x, obs.y], new_obstacle) <= (new_obs_size + obs.size):
            obs_overlaps = True
            break
    return auv_overlaps or shark_overlaps or obs_overlaps


def generate_rand_obstacles(auv_init_pos, shark_init_pos, num_of_obstacles):
    """
    """
    obstacle_array = []
    for _ in range(num_of_obstacles):
        obs_x = np.random.uniform(MIN_X, MAX_X)
        obs_y = np.random.uniform(MIN_Y, MAX_Y)
        obs_size = np.random.randint(1,5)
        while validate_new_obstacle([obs_x, obs_y], obs_size, auv_init_pos, shark_init_pos, obstacle_array):
            obs_x = np.random.uniform(MIN_X, MAX_X)
            obs_y = np.random.uniform(MIN_Y, MAX_Y)
        obstacle_array.append(Motion_plan_state(x = obs_x, y = obs_y, z=-5, size = obs_size))

    return obstacle_array  

"""
Class for building policy and target neural network
"""
class Neural_network(nn.Module):
    def __init__(self, input_size, output_size_v, output_size_w, hidden_layer_in = 400, hidden_layer_out = 300):
        """
        Initialize the Q neural network with input

        Parameter:
            input_size - int, the size of observation space
            output_size_v - int, the number of possible options for v
            output_size_y - int, the number of possible options for w
        """
        super().__init__()

        self.fc1 = nn.Linear(in_features = input_size, out_features = hidden_layer_in)
        self.bn1 = nn.LayerNorm(hidden_layer_in)

        # branch for selecting v
        self.fc2_v = nn.Linear(in_features = hidden_layer_in, out_features = hidden_layer_out) 
        self.bn2_v = nn.LayerNorm(hidden_layer_out)     
        self.out_v = nn.Linear(in_features = hidden_layer_out, out_features = output_size_v)
     
        # branch for selecting w
        self.fc2_w = nn.Linear(in_features = hidden_layer_in, out_features = hidden_layer_out)
        self.bn2_w = nn.LayerNorm(hidden_layer_out)     
        self.out_w = nn.Linear(in_features = hidden_layer_out, out_features = output_size_w)
        

    def forward(self, t):
        """
        Define the forward pass through the neural network

        Parameters:
            t - the state as a tensor
        """
        # pass through the layers then have relu applied to it
        # relu is the activation function that will turn any negative value to 0,
        #   and keep any positive value

        t = self.fc1(t)
        t = F.relu(t)
        t = self.bn1(t)

        # the neural network is separated into 2 separate branch
        t_v = self.fc2_v(t)
        t_v = F.relu(t_v)
        t_v = self.bn2_v(t_v)

        t_w = self.fc2_w(t)
        t_w = F.relu(t_w)
        t_w = self.bn2_w(t_w)
  
        # pass through the last layer, the output layer
        # output is a tensor of Q-Values for all the optinons for v/w
        t_v = self.out_v(t_v)  
        t_w = self.out_w(t_w)

        return torch.stack((t_v, t_w))



"""
    Class to define replay memeory for training the neural network
"""
class ReplayMemory():
    def __init__(self, capacity):
        self.capacity = capacity
        self.memory = []
        self.push_count = 0

    def push(self, experience):
        """
        Store an experience in the replay memory
        Will overwrite any oldest experience first if necessary

        Parameter:
            experience - namedtuples for storing experiences
        """
        # if there's space in the replay memory
        if len(self.memory) < self.capacity:
            self.memory.append(experience)
        else:
            # overwrite the oldest memory
            self.memory[self.push_count % self.capacity] = experience
        self.push_count += 1


    def sample(self, batch_size):
        """
        Randomly sample "batch_size" amount of experiences from replace memory

        Parameter: 
            batch_size - int, number of experiences that we want to sample from replace memory
        """
        return random.sample(self.memory, batch_size)


    def can_provide_sample(self, batch_size):
        """
        The replay memeory should only sample experiences when it has experiences greater or equal to batch_size

        Parameter: 
            batch_size - int, number of experiences that we want to sample from replace memory
        """
        return len(self.memory) >= batch_size



"""
For implementing epsilon greedy strategy in choosing an action
(exploration vs exploitation)
"""
class EpsilonGreedyStrategy():
    def __init__(self, start, end, decay):
        """
        Parameter:
            start - the start value of epsilon
            end - the end value of epsilon
            decay - the decay value of epsilon 
        """
        self.start = start
        self.end = end
        self.decay = decay

    def get_exploration_rate(self, current_step):
        """
        Calculate the exploration rate to determine whether the agent should
            explore or exploit in the environment
        """
        return self.end + (self.start - self.end) * \
            math.exp(-1. * current_step * self.decay)



"""
Class to represent the agent and decide its action in the environment
"""
class Agent():
    def __init__(self, actions_range_v, actions_range_w, device):
        """
        Parameter: 
            strategy - Epsilon Greedy Strategy class (decide whether we should explore the environment or if we should use the DQN)
            actions_range_v - int, the number of possible values for v that the agent can take
            actions_range_w - int, the number of possible values for w that the agent can take
            device - what we want to PyTorch to use for tensor calculation
        """
        # the agent's current step in the environment
        self.current_step = 0
        
        self.strategy = EpsilonGreedyStrategy(EPS_START, EPS_END, EPS_DECAY)
        
        self.actions_range_v = actions_range_v
        self.actions_range_w = actions_range_w
       
        self.device = device


    def select_action(self, state, policy_net):
        """
        Pick an action (index to select from array of options for v and from array of options for w)

        Parameters:
            state - tuples for auv position, shark (goal) position, and obstacles position
            policy_net - the neural network to determine the action

        Returns:
            a tensor representing the index for v action and the index for w action
                format: tensor([v_index, w_index])
        """
        rate = self.strategy.get_exploration_rate(self.current_step)
        # as the number of steps increases, the exploration rate will decrease
        self.current_step += 1

        if rate > random.random():
            # exploring the environment by randomly chosing an action
            if DEBUG:
                print("-----")
                print("randomly picking")
            v_action_index = random.choice(range(self.actions_range_v))
            w_action_index = random.choice(range(self.actions_range_w))

            return torch.tensor([v_action_index, w_action_index]).to(self.device) # explore

        else:
            # turn off gradient tracking bc we are using the model for inference instead of training
            # we don't need to keep track the gradient because we are not doing backpropagation to figure out the weight 
            # of each node yet
            with torch.no_grad():
                # convert the state to a flat tensor to prepare for passing into the neural network
                state = process_state_for_nn(state)

                # for the given "state"，the output will be Q values for each possible action (index for v and w)
                #   from the policy net
                output_weight = policy_net(state).to(self.device)
                if DEBUG:
                    print("-----")
                    print("exploiting")
                    print("Q values check - v")
                    print(output_weight[0])
                    print("Q values check - w")
                    print(output_weight[1])

                # output_weight[0] is for the v_index, output_weight[1] is for w_index
                # this is finding the index with the highest Q value
                v_action_index = torch.argmax(output_weight[0]).item()
                w_action_index = torch.argmax(output_weight[1]).item()

                return torch.tensor([v_action_index, w_action_index]).to(self.device) # explore  



"""
Class Wrapper for the auv RL environment
"""
class AuvEnvManager():
    def __init__(self, N_v, N_w, device):
        """
        Parameters: 
            device - what we want to PyTorch to use for tensor calculation
            N - 
            auv_init_pos - 
            shark_init_pos -
            obstacle_array - 
        """
        self.device = device

        # have access to behind-the-scenes dynamics of the environment 
        self.env = gym.make('gym_auv:auv-v0').unwrapped

        self.current_state = None
        self.done = False

        # an array of the form:
        #   [[array of options for v], [array of options for w]]
        # values of v and w for the agent to chose from
        self.possible_actions = self.env.actions_range(N_v, N_w)

    
    def init_env_randomly(self):
        auv_init_pos = Motion_plan_state(x = np.random.uniform(MIN_X, MAX_X), y = np.random.uniform(MIN_X, MAX_X), z = -5.0, theta = 0)
        shark_init_pos = Motion_plan_state(x = np.random.uniform(MIN_Y, MAX_Y), y = np.random.uniform(MIN_Y, MAX_Y), z = -5.0, theta = np.random.uniform(-np.pi, np.pi))
  
        obstacle_array = generate_rand_obstacles(auv_init_pos, shark_init_pos, NUM_OF_OBSTACLES)

        if DEBUG:
            print("===============================")
            print("Starting Positions")
            print(auv_init_pos)
            print(shark_init_pos)
            print(obstacle_array)
            print("===============================")
            text = input("stop")

        return self.env.init_env(auv_init_pos, shark_init_pos, obstacle_array)


    def reset(self):
        """
        Reset the environment and return the initial state
        """
        return self.env.reset()


    def close(self):
        self.env.close()


    def render(self, mode='human', print_state = True, live_graph = False):
        """
        Render the environment both as text in terminal and as a 3D graph if necessary

        Parameter:
            mode - string, modes for rendering, currently only supporting "human"
            live_graph - boolean, will display the 3D live_graph if True
        """
        state = self.env.render(mode, print_state)
        if live_graph: 
            self.env.render_3D_plot(state[0], state[1])
        return state


    def take_action(self, action, timestep):
        """
        Parameter: 
            action - tensor of the format: tensor([v_index, w_index])
                use the index from the action and take a step in environment
                based on the chosen values for v and w
        """
        v_action_index = action[0].item()
        w_action_index = action[1].item()
        v_action = self.possible_actions[0][v_action_index]
        w_action = self.possible_actions[1][w_action_index]
        
        # we only care about the reward and whether or not the episode has ended
        # action is a tensor, so item() returns the value of a tensor (which is just a number)
        self.current_state, reward, self.done, _ = self.env.step((v_action, w_action), timestep)

        if DEBUG:
            print("=========================")
            print("action v: ", v_action_index, " | ", v_action)  
            print("action w: ", w_action_index, " | ", w_action)  
            print("new state: ")
            print(self.current_state)
            print("reward: ")
            print(reward)
            print("=========================")

        # wrap reward into a tensor, so we have input and output to both be tensor
        return torch.tensor([reward], device=self.device).float()


    def get_state(self):
        """
        state will be represented as the difference bewteen 2 screens
            so we can calculate the velocity
        """
        return self.env.state

    
    def get_range_reward(self, auv_pos, goal_pos, old_range):
        reward = self.env.get_range_reward(auv_pos, goal_pos, old_range)

        return torch.tensor([reward], device=self.device).float()

    
    def get_range_time_reward(self, auv_pos, goal_pos, old_range, timestep):
        reward = self.env.get_range_time_reward(auv_pos, goal_pos, old_range, timestep)

        return torch.tensor([reward], device=self.device).float()


    def get_binary_reward(self, auv_pos, goal_pos):
        """
        Wrapper to convert the binary reward (-1 or 1) to a tensor

        Parameters:
            auv_pos - an array of the form [x, y, z, theta]
            goal_pos - an array of the same form, represent the target position that the auv is currently trying to reach
        """
        reward = self.env.get_binary_reward(auv_pos, goal_pos)

        return torch.tensor([reward], device=self.device).float()



"""
Use QValues class's 
"""
class QValues():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    @staticmethod
    def get_current(policy_net, states, actions):
        # actions is a tensor with this format: [[v_action_index1, w_action_index1], [v_action_index2, w_action_index2] ]
        # actions[:,:1] gets only the first element in the [v_action_index, w_action_index], 
        #   so we get all the v_action_index as a tensor
        # policy_net(states) gives all the predicted q-values for all the action outcome for a given state
        # policy_net(states).gather(dim=1, index=actions[:,:1]) gives us
        #   a tensor of the q-value corresponds to the state and action(specified by index=actions[:,:1]) pair 
        
        q_values_for_v = policy_net(states)[0].gather(dim=1, index=actions[:,:1])
        q_values_for_w = policy_net(states)[1].gather(dim=1, index=actions[:,1:2])
       
        return torch.stack((q_values_for_v, q_values_for_w), dim = 0)

    
    @staticmethod        
    def get_next(target_net, next_states):  
        # for each next state, we want to obtain the max q-value predicted by the target_net among all the possible next actions              
        # we want to know where the final states are bc we shouldn't pass them into the target net
       
        v_max_q_values = target_net(next_states)[0].max(dim=1)[0].detach()
        w_max_q_values = target_net(next_states)[1].max(dim=1)[0].detach()
       
        return torch.stack((v_max_q_values, w_max_q_values), dim = 0)



class DQN():
    def __init__(self, N_v, N_w):
        # initialize the policy network and the target network
        self.policy_net = Neural_network(STATE_SIZE, N_v, N_w).to(DEVICE)
        self.target_net = Neural_network(STATE_SIZE, N_v, N_w).to(DEVICE)

        self.hard_update(self.target_net, self.policy_net)
        self.target_net.eval()

        self.policy_net_optim = optim.Adam(params = self.policy_net.parameters(), lr = LEARNING_RATE)

        self.memory = ReplayMemory(MEMORY_SIZE)

        # set up the environment
        self.em = AuvEnvManager(N_v, N_w, DEVICE)

        self.agent = Agent(N_v, N_w, DEVICE)


    def hard_update(self, target, source):
        """
        Make sure that the target have the same parameters as the source
            Used to initialize the target networks for the actor and critic
        """
        for target_param, param in zip(target.parameters(), source.parameters()):
            target_param.data.copy_(param.data)


    def load_trained_network(self):
        """
        Load already trained neural network
        """
        print("Loading previously trained neural network...")
        self.agent.strategy.start = EPS_DECAY + 0.001
        self.policy_net.load_state_dict(torch.load('checkpoint_policy.pth'))
        self.target_net.load_state_dict(torch.load('checkpoint_target.pth'))


    def save_real_experiece(self, state, next_state, action, timestep):
        old_range = calculate_range(state[0], state[1])

        reward = self.em.get_range_time_reward(next_state[0], next_state[1], old_range, timestep)

        self.memory.push(Experience(process_state_for_nn(state), action, process_state_for_nn(next_state), reward))

    
    def generate_extra_goals(self, time_step, next_state_array):
        additional_goals = []

        possible_goals_to_sample = next_state_array[time_step+1: ]

        # only sample additional goals if there are enough to sample
        # TODO: slightly modified from our previous implementation of HER, maybe this is better?
        if len(possible_goals_to_sample) >= NUM_GOALS_SAMPLED_HER:
            additional_goals = random.sample(possible_goals_to_sample, k = NUM_GOALS_SAMPLED_HER)
        
        return additional_goals

    
    def store_extra_goals_HER(self, state, next_state, action, additional_goals, timestep):
        for goal in additional_goals:
            new_curr_state = (state[0], goal[0], state[2])
                
            new_next_state = (next_state[0], goal[0], next_state[2])
            
            old_range = calculate_range(new_curr_state[0], new_curr_state[1])

            reward = self.em.get_range_time_reward(new_next_state[0], new_next_state[1], old_range, timestep)
            
            self.memory.push(Experience(process_state_for_nn(new_curr_state), action, process_state_for_nn(new_next_state), reward))
    

    def update_neural_net(self):
        if self.memory.can_provide_sample(BATCH_SIZE):
            # Sample random batch from replay memory.
            experiences = self.memory.sample(BATCH_SIZE)
            
            # extract states, actions, rewards, next_states into their own individual tensors from experiences batch
            states, actions, rewards, next_states = extract_tensors(experiences)

            # Pass batch of preprocessed states to policy network.
            # return the q value for the given state-action pair by passing throught the policy net
            current_q_values = QValues.get_current(self.policy_net, states, actions)
        
            next_q_values = QValues.get_next(self.target_net, next_states)
            
            target_q_values_v = (next_q_values[0] * GAMMA) + rewards
            target_q_values_w = (next_q_values[1] * GAMMA) + rewards

            loss_v = F.mse_loss(current_q_values[0], target_q_values_v.unsqueeze(1))
            loss_w = F.mse_loss(current_q_values[1], target_q_values_w.unsqueeze(1))

            loss_total = loss_v + loss_w
            self.loss_in_eps.append(loss_total.item())

            self.policy_net_optim.zero_grad()
            loss_total.backward()
            self.policy_net_optim.step()


    def train(self, num_episodes, max_step, load_prev_training = False, use_HER = True):
        self.episode_durations = []
        self.avg_loss_in_training = []

        if load_prev_training:
            # if we want to continue training an already trained network
            self.load_trained_network()
        
        for eps in range(num_episodes):
            # initialize the starting point of the shark and the auv randomly
            # receive initial observation state s1 
            state = self.em.init_env_randomly()

            # reward received in this episode
            eps_reward = 0

            action_array = []
            next_state_array = []

            # determine how many steps we should run HER
            # by default, it will be "max_step" - 1 because in the first loop, we start at t=1
            iteration = max_step - 1

            self.loss_in_eps = []

            for t in range(1, max_step):
                action = self.agent.select_action(state, self.policy_net)
                action_array.append(action)

                score = self.em.take_action(action, t)

                next_state = self.em.get_state()
                next_state_array.append(next_state)

                if eps % RENDER_EVERY == 0:
                    self.em.render(print_state = False, live_graph = True)

                state = next_state

                if self.em.done:
                    iteration = t
                    break
            
            self.episode_durations.append(iteration)

            # reset the state before we start updating the neural network
            state = self.em.reset()

            for t in range(iteration):
                action = action_array[t]
                next_state = next_state_array[t]

                # store the actual experience that the auv has in the first loop into the memory
                self.save_real_experiece(state, next_state, action, t)

                if use_HER:
                    additional_goals = self.generate_extra_goals(t, next_state_array)
                    self.store_extra_goals_HER(state, next_state, action, additional_goals, t)

                state = next_state

                self.update_neural_net()

            if self.loss_in_eps != []:
                avg_loss = np.mean(self.loss_in_eps)
                self.avg_loss_in_training.append(avg_loss)
                print("+++++++++++++++++++++++++++++")
                print("Episode # ", eps, "end with reward: ", score, "average loss", avg_loss, " used time: ", iteration)
                print("+++++++++++++++++++++++++++++")
            else:
                print("+++++++++++++++++++++++++++++")
                print("Episode # ", eps, "end with reward: ", score, "average loss nan", " used time: ", iteration)
                print("+++++++++++++++++++++++++++++")

            if eps % TARGET_UPDATE == 0:
                print("UPDATE TARGET NETWORK")
                self.target_net.load_state_dict(self.policy_net.state_dict())

            if eps % SAVE_EVERY == 0:
                save_model(self.policy_net, self.target_net)

            # if eps % RENDER_EVERY ==0:
            #     text = input("manual stop")
            # else:
            #     time.sleep(0.5)

        save_model(self.policy_net, self.target_net)
        self.em.close()
        print(self.episode_durations)
        print("average loss")
        print(self.avg_loss_in_training)

    
def main():
    dpn = DQN(N_V, N_W)
    dpn.train(NUM_OF_EPISODES, MAX_STEP, load_prev_training=True)

if __name__ == "__main__":
    main()
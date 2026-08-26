from simulator.propagation import PropagationModel



model = PropagationModel()



# Gateway

gw_x = 1000

gw_y = 1000



# Node

node_x = 1500

node_y = 1200



distance = model.calculate_distance(

    node_x,

    node_y,

    gw_x,

    gw_y

)



loss = model.calculate_path_loss(

    distance

)



print(
    "===== Propagation Test ====="
)


print(

    f"Distance: {distance:.2f} m"

)


print(

    f"Path Loss: {loss:.2f} dB"

)

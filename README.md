A small tool, originating from the idea to re-create the Velocity Overlay known in the Source Movement Scene. 


Troubleshooting:

-The Object you want to measure the speed of has to have positional keyframes. Movement resulting from Physics Simulations or Parenting will result in zeros (if they are not baked to keyframes). 

-In order to transfer the data block to the Shader Editor, you need to select an Object with a active Material.

-The driver that drives the change of the TextObject will not be saved between sessions. If the TextObject will not be re-named, generating it again will update the text again with all changes staying in place.

I made a youtube video about it with strong focus on the application in Source Surf and other Source Movement Mods.
https://www.youtube.com/watch?v=iEo0BfP4S18

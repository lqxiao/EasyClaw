# Benchmark Spec for Agent

## Task 

Your task is to build a benchmark for an image generation/edit for shopping tasks. There are 8 subtasks, you are gonna create 30 samples for each subtask. The following table describe the content of the task. The input for edit task, is an instruction (see Example column), plus 1-4 images (user full body portrait or user home picture is the 1st), and output is an edited image. The input for generation is one text instruction and output is a generated image. Your task is to build the input, you do not need to generate output. 

## Your workflow: 

1. for tasks, write diverse instructions like users, put instruction to .csv file. Keep the instruction diverse and real. 
2. for the instructions, crawl images from amazon.com (all your images should comes from amazon.com, do not crawl other sources, you pick model/showroom images to mimic user full body portrait or user home picture), pair them up to be input.
4. check samples one by one to make sure the instruction match the image. It the sample does not make sense, fix it.  

Type	Benchmark	Task	Example	Input
Edit	Virtual Try-On	Place one or more clothing items onto a user body	Put this denim jacket on me	input: instruction like example; a user Full-body portrait ; 1 -> 3 clothing product pictures; 
Edit	Outfit Styling	Suggest outfit styling combinations given an anchor clothing item	Generate outfits around a jacket	input: instrcution like examples; a user Full-body portrait
Edit	Garment Editing	Modify clothing attributes in an image such as color, fabric, or fit while preserving the garment structure	Change a red dress to blue silk	input: instrcution like examples; a user Full-body portrait
Edit	In-Scene Product Placement	Insert products into a user-provided home photo with correct scale, lighting, and perspective	Place a floor lamp in a living room photo	input: instruction like example; a home picture;  1-> 3 product pictures;
Edit	Interior Style Generation	Transform a user-provided home image into a different interior design style	Generate room designs around a sofa	input: instrcution like examples; a home image
Edit	Home Editing	Modify specific elements of a home scene such as furniture, decor, color palette, or materials	Replace a coffee table with a marble one	input: instrcution like examples; a home image
Edit	Visual Product Search	Search for exact match products based on image	Find the same sneakers from a photo	input: instruction like examples; an image with any clothings/home furniture/home decer 
Generation	Shoppable Posts	Generate inspirational visual posts that contain multiple styled products that can be purchased	Create a “Baking essentials” shoppable collage	input: instruction

## Your Delivery 

A folder under ./workspace/MISSIONS/build_mm_shopping_benchmark with following structure: 
- mm_shopping_benchmark_train
    -samples.csv
    -images
        -<image1_description>.png
        -<image2_description>.png

the csv contain columns: Type, benchmark, Task, Instruction, Images (a list of images under /image folder). 

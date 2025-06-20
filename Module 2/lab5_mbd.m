%% Task 1: Creating a Simple Function
a=3;
b=5;
result=mysimplefunction(a,b);
disp(result);
%% Task 2: Function Inputs and Outputs
reduis= input('enter a positive number');
resultarea= calcArea(reduis);
disp(['the area of circle is ',num2str(resultarea)]);
%% Task 3: Function with Multiple Outputs
Data = [5, 10, 15, 20, 25];
[meanVal, stdVal] = computeStatistics(Data);
disp(['Mean: ', num2str(meanVal)]);
disp(['Standard Deviation: ', num2str(stdVal)]);
%% Task 4: Nested Functions
outerfunction()
%% Task 5: Function Handles
data = [1, 2, 3, 4, 5];
squares = applyFunction(@(x) x^2, data);
disp(['Squares: ', num2str(squares)]);
cubes = applyFunction(@(x) x^3, data);
disp(['Cubes: ', num2str(cubes)]);
multiplied = applyFunction(@(x) x * 10, data);
disp(['Scaled by 10: ', num2str(multiplied)]);

%% Task 6: Anonymous Functions
triangleArea = @(base, height) 0.5 * base * height;
area1 = triangleArea(10, 5);
disp(['Area 1: ', num2str(area1)]);  
area2 = triangleArea(7, 3);
disp(['Area 2: ', num2str(area2)]);  
area3 = triangleArea(12, 8);
disp(['Area 3: ', num2str(area3)]);  

%% Task 7: Using Built-in Functions
data = [4, 12, 7, 19, 3, 10];
maximumVal = max(data);
minimumVal = min(data);
result = sum(data);
disp(['Vector: ', num2str(data)]);
disp(['Maximum value: ', num2str(maximumVal)]);
disp(['Minimum value: ', num2str(minimumVal)]);
disp(['Sum of all elements: ', num2str(result)]);

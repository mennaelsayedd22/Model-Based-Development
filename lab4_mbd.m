%% task 1 while loop
i=2;
while i<=20
    EvenNumber= i;
    disp(['even numbers are ',num2str(EvenNumber)]);
    i=i+2;
end

    n = input('Enter a non-negative integer to calculate its factorial: ');
    j=1;
    factorialResult=1;
    while j <= n
    factorialResult = factorialResult * j;
    j = j + 1;
    end
disp(['Factorial of ', num2str(n), ' is: ', num2str(factorialResult)]);

%% task 2 switch statment
mode= input('enter one of the following to know the cost(car,plane,train,bus)','s');
switch mode
    case 'car'
        disp('the cost is 1000le')
    case "plane"
        disp('the cost is 500' )
    case 'train'
        disp('the cost is 300')
    case 'bus'
        disp('the cost is 200')
end

color=input('entera color code (r, g, b, y, k)','s');
switch color 
    case 'r'
        disp('color is red')
    case 'g'
        disp('color is green')
    case 'b'
 disp('color is blue')
    case 'y'
        disp('color is yellow')
    case 'k'
        disp('color is black ')
end
%% additional task 
mode = input('Enter mode of transport (car, plane, train, bus): ', 's');
miles = input('Enter the number of miles: ');
costPerMile = 0;
switch mode
    case 'car'
        costPerMile = 5;      
    case 'plane'
        costPerMile = 10;
    case 'train'
        costPerMile = 3;
    case 'bus'
        costPerMile = 2;
    otherwise
        disp('Invalid mode of transport.');
end

if costPerMile > 0
    totalCost = costPerMile * miles;
    disp(['Total cost for ', mode, ' is ', num2str(totalCost), ' LE']);
end

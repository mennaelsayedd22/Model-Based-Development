%% 1. Cell Arrays:
CellArray={1,5,[1 2 3],'menna',pi};
disp(CellArray(1));
disp(CellArray(2));
disp(CellArray(3));
disp(CellArray(4));
disp(CellArray(5));
 
%% 2. Structures:
Person.name="menna";
Person.age=22;
Person.city="cairo";
disp('my name is ');
disp(Person.name);
disp('my age is ');
disp(Person.age);
disp('my city is ');
disp(Person.city);
%% 3. Character Data:
CharArray1="menna"';
CharArray2=" elsayed";
TotalArray= strcat(CharArray1 , CharArray2);
%% 4. Conditional Statements  (If):
X=input('enter an even number');
if mod(X,2)==0
   disp('it is an even number');
   else 
       disp('it is an odd number')
end

%% 5. For Loops:
for A=1:10
    disp(['Number is ' , num2str(A)]);
end

%% 6. Basic Plotting:
x = 0:0.1:2*pi;
y = sin(x);
plot(x, y, 'b-', 'LineWidth', 2);
xlabel('x in rad');
ylabel('sin(x)');
title('Sine Wave');
legend('sin(x)');
grid on;


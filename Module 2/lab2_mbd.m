%% Numeric Types:
intVar= int16(19);
doubleVar=3.1458;
x=class(intVar)
y=class(doubleVar)
%% Creating Numeric Arrays:
RowVector=[2 4 6 8 10]
ColumnVector=[2;3;5;7;11]
disp(['even numbers are ',num2str(RowVector)])
disp(['prime numbers are ' , num2str(ColumnVector')])
%% Specialized Matrix Functions:
Z= eye(3)
M=magic(3)
disp('identityMatrix:');
disp(Z);
disp('magicSquare:');
disp(M);
%% Matrix Concatenation:
combinedVector = [RowVector, ColumnVector'];  % Concatenate as row vector (transpose column to row)
disp('combinedVector:');
disp(combinedVector);

combinedMatrix = [Z ; M];  % Vertical concatenation
disp('combinedMatri x:');
disp(combinedMatrix);

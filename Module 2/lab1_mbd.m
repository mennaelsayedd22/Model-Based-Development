%% part1
MatrixA=[3 2 1; 6 5 4; 9 8 7]
MatrixB=[12 11 10; 15 14 13; 18 17 16]
MatrixSUM = MatrixA + MatrixB
%% part 2
rowVector=(1:5)
columnVector=(6:10)'
horizontalConcet= horzcat(rowVector,columnVector')
%% part 3
originMatrix= rand(2,2)
repeatedMatrix=repmat(originMatrix,2,2)
%% part 4
MatrixA=[3 2 1; 6 5 4; 9 8 7]
identityMatrix= eye(3,3)
matrixProduct= identityMatrix.*MatrixA

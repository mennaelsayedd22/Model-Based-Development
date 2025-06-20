function outerFunction()
    a = 7;
    b = 12;
    result = innerFunction(a, b);
    disp(['The sum of ', num2str(a), ' and ', num2str(b), ' is: ', num2str(result)]);
    function sum = innerFunction(x, y)
        sum = x + y;
    end
end

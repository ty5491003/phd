# Compiler Fuzzing through Deep Learning: Artifact


这个目录包含着ISSTA'18这篇论文的artiface supporting。
包括用于评估我们生成器和测试组件的一个缩小规模的数据集，其完整数据集非常大（未压缩下>200 GB）。
可以阅读本文件第四节获取更详细的说明。


## 1. Artifact Contents

 * [01_evaluate_generator](01_evaluate_generator.py): 训练神经网络模型以生成程序的演示.

 * [02_evaluate_harness](02_evaluate_harness.py): 在OpenCL测试平台上执行测试用例的演示.

 * [03_evaluate_results](03_evaluate_results.py): 我们的差异测试方法的演示。先前演示的结果与我们自己的论文数据结合起来进行差异测试.


## 2. Installation

参见Readme.md文件，使用babel来构建整个系统.


## 3. Evaluating the artifact

### 3.1. Evaluate the generator
*(大约运行时间:2小时)*

通过运行以下程序来评估DeepSmith生成器:
```sh
$ bazel run //docs/2018_07_issta/artifact_evaluation:01_evaluate_generator
```

该程序使用一个从我们的GitHub语料库中随机选择的1000个内核的小型OpenCL语料库，对该语料库进行预处理，在预处理的语料库上训练模型，并生成1024个新的OpenCL测试用例。

我们减小了语料库和网络的大小，因此在CPU上进行训练大约需要2个小时。 我们用于生成论文中所用程序的模型要大得多（每层512个节点，而不是256个节点），受更多数据训练（3000万令牌而不是450万令牌），并且受训时间更长（50个epoch，而不是20个epoch）。 因此，这种小模型的输出质量要低得多，生成的语法正确的程序很少。

训练模型可以随时中断和恢复。 训练后，无需重新训练模型。 训练后的模型存储在：
`/tmp/phd/docs/2018_07_issta/artifact_evaluation/clgen`.

生成的程序被写入目录： 
`/tmp/phd/docs/2018_07_issta/artifact_evaluation/generated_kernels`. 

每个kernal生成两个测试用例，一个单线程，一个多线程。 生成的testcase被写入到：
`/tmp/phd/docs/2018_07_issta/artifact_evaluation/generated_testcases`.

#### 3.1.1. 拓展评估 (可选)

通过更改模型中定义的参数：
`//docs/2018_07_issta/artifact_evaluation/data/clgen.pbtxt`，
你可以评估不同结构和不同训练时间的模型的输出，文件的架构被定义在：
`//deeplearning/deepsmith/proto/generator.proto`.

你也可以通过增加额外的opencl文件或者删除文件来修改数据集。


### 3.2. Evaluate the harness

*(approximate runtime: 30 minutes)*


Evaluate the DeepSmith harness by running a set of test cases using an 
Oclgrind testbed:

```sh
$ bazel run //docs/2018_07_issta/artifact_evaluation/02_evaluate_harness
```

The program runs the 1024 generated testcases from the previous program, plus
a nuber of test cases taken from the experimental data we used in the paper, 
located in the directory 
`//docs/2018_07_issta/artifact_evaluation/data/testcases`. We include 
pre-generated test cases so that we can differential test the results in the
next stage of the evaluation.

The results of execution are written to the directory
`/tmp/phd/docs/2018_07_issta/artifact_evaluation/results`. Each file in this
directory stores the result of a single test case execution. The schema for
these files is defined in `//deeplearning/deepsmith/proto/deepsmith.proto`.


#### 3.2.1. Extended Evaluation (optional)

You could add more test cases to execute, or manually change the contents of
testcases, for example, by changing the `src` field for a testcase to change
the OpenCL kernel which is evaluated.


### 3.3. Evaluate the results

*(approximate runtime: 5 minutes)*

Evaluate the DeepSmith difftester using:

```sh
$ bazel run //docs/2018_07_issta/artifact_evaluation/03_evaluate_results
```

The program evaluates the results generated from your local system in the
previous experiment, and differential tests the outputs against the data we
used in the paper. At the end of execution, the program prints a table of
classifications, using the same format as Table 2 of the paper. Individually
classified results are written to
`/tmp/phd/docs/2018_07_issta/artifact_evaluation/difftest_classifications/<class>/<device>/<±>/`.


#### 3.3.1. Extended Evaluation (optional)

The evaluation program difftests all results files from these directories:

```sh
/tmp/phd/docs/2018_07_issta/artifact_evaluation/difftest_classifications  # Results from your system
//docs/2018_07_issta/artifact_evaluation/data/our_results  # Results from our machines
```

You could add new results to these directories by repeatedly running the first
two programs. Alternatively you could modify individual results files, such as 
by changing the returncode to simulate different test case outcomes, and 
observe how that influences the classification of results.


## 4. Further Reading and References

DeepSmith目前正在进行彻底的重写，以支持更多的语言并添加新功能，例如在多台计算机上分布测试。 正在进行的可以在以下位置找到:

    https://github.com/ChrisCummins/phd/tree/master/deeplearning/deepsmith

在我们论文中用来生成数据的代码存放在：

    https://github.com/ChrisCummins/phd/tree/master/experimental/dsmith


## 5. License

Copyright 2017, 2018 Chris Cummins <chrisc.101@gmail.com>.

Released under the terms of the GPLv3 license. See
[LICENSE](/docs/2018_07_issta/artifact_evaluation/LICENSE) for details.

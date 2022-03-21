from dataclasses import dataclass
import logging
import os
from pathlib import Path
import shutil
from typing import List
from subprocess import CompletedProcess, run

from testers.BaseExecutor import BaseExecutor
from utils.ExecutionContext import console
from utils.TraceToLine import  open_ascii
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule

logger = logging.getLogger("pipex-fso")


def run_bash(command):
	return run(command, capture_output=True, shell="True", encoding="ascii", errors="backslashreplace")


@dataclass
class TestCase:
	params: List[str]
	description: str
	path: str = os.environ['PATH']


class Fsoares(BaseExecutor):

	name = 'fsoares'
	folder = 'fsoares'
	git_url = 'my own tests'

	def __init__(self, tests_dir, temp_dir, to_execute, missing) -> None:
		super().__init__(tests_dir, temp_dir, to_execute, missing)

	def execute(self):
		tests = self.get_tests()
		shutil.copy(self.temp_dir / ".." / 'pipex', self.temp_dir)
		# create the weird permission files (or change them)
		result = []
		for test in tests:
			result.append(self.execute_test(test))
		os.chdir(self.temp_dir)

		test_result = self.show_test_results(result)
		return []

	def show_test_results(self, results):
		errors = False
		for result in results:
			text = Text()
			if result[1]:
				console.print(Rule("[b red]Error[/b red]: " + result[0].description, style="red"))
				for error in result[1]:
					text.append(error[0] + ": " + error[1] + "---" + error[2])
				console.print(text)
				errors = True
		return errors

	def execute_test(self, test):
		infile, cmd1, cmd2, outfile = test.params
		#TODO: change path
		#execute native
		self.reset_test(test)
		native = run_bash(f"< {infile} {cmd1} | {cmd2} > {outfile}")
		with open_ascii("outfile.txt") as r:
			native_outfile = r.read()

		#execute pipex
		self.reset_test(test)
		pipex = run_bash(f'./pipex {infile} "{cmd1}" "{cmd2}" {outfile}')
		with open_ascii("outfile.txt") as r:
			pipex_outfile = r.read()

		return self.compare_output(test, native, native_outfile, pipex, pipex_outfile)

	def reset_test(self, test):
		os.chdir(self.temp_dir)
		dirpath = Path('temp')
		if dirpath.exists() and dirpath.is_dir():
			shutil.rmtree(dirpath)
		files = os.listdir('.')
		os.mkdir('temp')
		for file in files:
			shutil.copy(file, 'temp')
		os.chdir('temp')

	def compare_output(self, test, native: CompletedProcess, native_outfile, pipex, pipex_outfile):
		problems = []
		if native.stdout != pipex.stdout:
			problems.append(["Different stdout", native.stdout, pipex.stdout])
		if len(native.stderr.splitlines()) != len(pipex.stderr.splitlines()):
			problems.append(["Different stderr", native.stderr, pipex.stderr])
		if native.returncode != pipex.returncode:
			problems.append(["Different return code", str(native.returncode), str(pipex.returncode)])
		if native_outfile != pipex_outfile:
			problems.append(["Different outfile", native_outfile, pipex_outfile])
		return [test, problems]

	def get_tests(self):
		return [
		    TestCase(['infile.txt', 'cat', 'wc', 'outfile.txt'],
		             'Normal parameters, simple commands, everything should go ok'),
		    TestCase(['infile.txt', 'cat', 'wc', 'inexistent.txt'], "Output file does not exist"),
		    TestCase(['infile.txt', "sed 's/And/But/'", 'grep But', 'outfile.txt'],
		             'Normal parameters, commands with arguments, everything should go ok'),
		    TestCase(['infile.txt', "./script.sh", 'wc', 'outfile.txt'], 'Command that is in the same folder'),
		    TestCase(['infile.txt', (self.tests_dir / "script.sh").resolve(), 'wc', 'outfile.txt'],
		             'Command that contains the complete path'),
		    TestCase(['no_in', 'cat', 'wc', 'outfile.txt'], "Input files does not exist"),
		    TestCase(['infile.txt', 'non_existent_comm', 'wc', 'outfile.txt'], "first command does not exist"),
		    TestCase(['infile.txt', 'cat', 'non_existent_comm', 'outfile.txt'], "second command does not exist"),
		    TestCase(['no_r_perm', 'cat', 'wc', 'outfile.txt'], "Input files does not have read permissions"),
		    TestCase(['infile.txt', 'cat', 'wc', 'no_w_perm'], "Output files does not have write permissions"),
		    TestCase(['infile.txt', './no_x_script.sh', 'wc', 'outfile.txt'],
		             "The first command does not have execution permission"),
		    TestCase(['infile.txt', 'cat', './no_x_script.sh', 'outfile.txt'],
		             "The second command does not have execution permission"),
		    TestCase(['infile.txt', './middle_fail.sh', 'wc', 'outfile.txt'],
		             "The first commands fails in the middle of executing, but produces some output"),
		    TestCase(['infile.txt', 'cat', './middle_fail.sh', 'outfile.txt'],
		             "The second commands fails in the middle of executing, but produces some output"),
		    TestCase(['infile.txt', './script.sh', './script.sh', 'outfile.txt'],
		             "The PATH variable is empty, but the scrips are local",
		             path=""),
		    TestCase(['infile.txt', 'cat', 'wc', 'outfile.txt'], "The PATH variable is empty", path=""),
		    TestCase(['infile.txt', './script.sh', './script.sh', 'outfile.txt'],
		             "The PATH variable does not exist with local scripts",
		             path=None),
		    TestCase(['infile.txt', 'cat', 'wc', 'outfile.txt'],
		             "The PATH variable does not exist with normal commans",
		             path=None),
		    TestCase(['infile.txt', 'cat', 'script.sh', 'outfile.txt'],
		             "Should not match the command name if it does not have a dot before the name"),
		    TestCase(['infile.txt', 'cat', 'uname', 'outfile.txt'],
		             "It searchs the command by the order in PATH",
		             path=f"{self.tests_dir}:{os.environ['PATH']}"),
		    TestCase(['infile.txt', 'cat', 'wc', 'outfile.txt'],
		             "The PATH is shorter and does not have /usr/bin/ (and this wc) in it",
		             path=f"/bin"),
		    TestCase(['infile.txt', 'cat', 'wc', 'outfile.txt'],
		             "The PATH has '/' at the end of each entry",
		             path="/:".join(os.environ["PATH"].split(':'))),
		]

	at define on the videos c08
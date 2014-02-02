import fuzzer
import unittest, sqlite3, os

class TestFuzzer(unittest.TestCase):
    def setUp(self):
    	self.fuzzer=fuzzer.Fuzzer(database="test_fuzzer_db.db")
        self.connection = sqlite3.connect("test_fuzzer_db.db")
    def tearDown(self):
        self.connection.close()
        os.remove("test_fuzzer_db.db")
    def test_initialize(self):
        """
        Test to make sure that database is created for the fuzzer.
        """
    	self.assertTrue(
            self.fuzzer.initialize()
        )

        check_cursor = self.connection.cursor()

        self.assertTrue(
            len(
                check_cursor.execute(
                    "SELECT name FROM sqlite_master\
                     WHERE type='table';"
                ).fetchall()
            ) == 1,
            msg="The table should be created for the fuzzer."
        )
    def test_fuzz(self):
        """
        Test to make sure that the fuzzer works as expected (proper output).
        """
    	self.fuzzer.initialize()


        for number, result in enumerate(self.fuzzer.fuzz()):
            if number >= 600:
                break
            for character in result.value:
                self.assertTrue(
                    ord(character) in range(256),
                    msg="Default parameters should return ASCII characters."
                )

        prohibited = ["a", "b"]
        for number, result in enumerate(
                                   self.fuzzer.fuzz(
                                        prohibit=prohibited
                                   )
                              ):
            if number >= 600:
                break
            for character in result.value:
                self.assertTrue(
                    character not in prohibited,
                    msg="A character in the result was not supposed to be present."
                )
        def testing_evaluator(value):
            return chr(value)
        for number, result in enumerate(
                                  self.fuzzer.fuzz(
                                       character_evaluator=testing_evaluator
                                  )
                              ):
            if number >= 600:
                break
            for character in result.value:
                self.assertTrue(
                    ord(character) in range(256),
                    msg="A custom character_evaluator should work."
                )






if __name__ == '__main___':
	unittest.main()